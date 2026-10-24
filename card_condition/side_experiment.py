"""Offline single-side baseline; human boxes are required, never inferred."""
import hashlib
import json
from pathlib import Path
import time

from PIL import Image, ImageOps
import torch
from torch import nn
from torchvision.transforms.functional import to_tensor, normalize

from .data import LABELS, load_manifest, training_readiness
from .model import device_for
from .side_model import backbone_for
from .regions import GLARE_AREAS, VISIBILITY_ISSUES, validate_annotations


def side_rows(manifest, splits=None):
    rows, skipped = [], []
    for row in load_manifest(manifest, splits=splits):
        if row.get('excluded'):
            continue
        annotations = validate_annotations(row.get('side_annotations', {}), row)
        for side in ('front', 'back'):
            a = annotations.get(side)
            if not a or a['box'] is None or a['labels']['gradable'] is None:
                skipped.append(row['id']+'/'+side)
                continue
            rows.append({'id':row['id']+'/'+side, 'group':row['group'], 'split':row['split'],
                         'image':a['image'], 'box':a['box'], 'labels':a['labels'],
                         'visibility_issues':a.get('visibility_issues', []),
                         'glare_areas':a.get('glare_areas', []),
                         'card_id':row['id'], '_image_hashes':row['_image_hashes']})
    plan = training_readiness(rows)
    return rows, skipped, plan


def prepared_image(image, box, crop, image_size):
    if image_size not in (None, 224, 448):
        raise ValueError('image_size must be 224 or 448')
    if crop:
        w,h = image.size
        # Preserve outermost border pixels when mapping normalized coordinates.
        import math
        region = (math.floor(box[0]*w), math.floor(box[1]*h),
                  math.ceil(box[2]*w), math.ceil(box[3]*h))
        image = image.crop(region)
    if image_size is not None:
        image = ImageOps.pad(image,(image_size,image_size),method=Image.Resampling.BILINEAR,color=(128,128,128))
    return image


def side_image(path, box, crop, image_size=224):
    if image_size not in (None, 224, 448):
        raise ValueError('image_size must be 224 or 448')
    with Image.open(path) as source:
        return prepared_image(ImageOps.exif_transpose(source).convert('RGB'), box, crop, image_size)


def side_tensor(path, box, crop, image_size=224):
    image = side_image(path, box, crop, image_size)
    return normalize(to_tensor(image),[.485,.456,.406],[.229,.224,.225])


def view_tensors(path, boxes, image_size=224):
    """Decode once per view group; retain no image across requests."""
    if image_size not in (224, 448):
        raise ValueError('image_size must be 224 or 448')
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    for box in boxes:
        view = prepared_image(image, box, True, image_size)
        yield normalize(to_tensor(view),[.485,.456,.406],[.229,.224,.225])


def side_views(path, box, crop=False, tiles=False):
    if not tiles:
        return side_tensor(path, box, crop).unsqueeze(0)
    # Fixed overlapping quadrants preserve border coverage; no defect localization.
    left, top, right, bottom = box
    w, h = right-left, bottom-top
    boxes = [box] + [[left+x*w, top+y*h, left+(x+.6)*w, top+(y+.6)*h]
                     for x,y in ((0,0),(.4,0),(0,.4),(.4,.4))]
    return torch.stack([side_tensor(path, region, True) for region in boxes])


def score(rows, probabilities, supported):
    metrics={k:dict(tp=0,tn=0,fp=0,fn=0) for k in supported};predictions=[]
    for row,probs in zip(rows,probabilities):
        for k,m in metrics.items():
            truth=row['labels'][k]
            if truth is not None:
                pred=int(probs[LABELS.index(k)]>=.5)
                m[('t' if pred==truth else 'f')+('p' if pred else 'n')]+=1
        predictions.append({'id':row['id'],'labels':row['labels'],'probabilities':{k:probs[i] if k in supported else None for i,k in enumerate(LABELS)}})
    return metrics, predictions


def training_balance(rows, supported):
    counts = {k:{'positive':0,'negative':0,'unknown':0} for k in LABELS}
    for row in rows:
        if row['split'] != 'train':
            continue
        for k in LABELS:
            value = row['labels'][k]
            counts[k]['unknown' if value is None else ('positive' if value else 'negative')] += 1
    weights = [counts[k]['negative']/counts[k]['positive']
               if k in supported and counts[k]['positive'] and counts[k]['negative'] else 1.0
               for k in LABELS]
    return counts, weights


def visibility_report(rows, probabilities, supported):
    """Diagnostic slices only; unknown labels never become negative examples."""
    validation = [r for r in rows if r['split'] == 'val']
    result = {}
    for field, values, prefix in (('visibility_issues', VISIBILITY_ISSUES, 'visibility'),
                                  ('glare_areas', GLARE_AREAS, 'glare_area')):
        counts = {phase: {value: sum(value in r.get(field, []) for r in rows if r['split'] == phase)
                          for value in values} for phase in ('train', 'val')}
        metrics = {}
        for value in values:
            selected = [(r, p) for r, p in zip(validation, probabilities) if value in r.get(field, [])]
            if selected:
                metrics[value] = score([r for r, _ in selected], [p for _, p in selected], supported)[0]
        result[prefix + '_counts'] = counts
        result[prefix + '_validation_metrics'] = metrics
    result['glare_location_coverage'] = {
        phase: {'located': sum(bool(r.get('glare_areas')) for r in rows
                               if r['split'] == phase and 'glare' in r['visibility_issues']),
                'unlocated_ids': [r['id'] for r in rows if r['split'] == phase
                                  and 'glare' in r['visibility_issues'] and not r.get('glare_areas')]}
        for phase in ('train', 'val')}
    result['glare_area_unknown_labels'] = {
        area: {k: sum(r['labels'][k] is None for r in validation if area in r.get('glare_areas', []))
               for k in supported} for area in GLARE_AREAS if result['glare_area_counts']['val'][area]}
    return result


def experiment(manifest, output, crop=False, device='auto', epochs=5, pretrained=True, tiles=False, balance=False, fine_tune_last=False, backbone_name='mobilenet_v3_small'):
    if crop and tiles:
        raise ValueError('Choose crop or tiles, not both')
    if epochs < 1:
        raise ValueError('epochs must be positive')
    if fine_tune_last and backbone_name != 'mobilenet_v3_small':
        raise ValueError('Last-block fine-tuning is only implemented for MobileNet')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    rows, skipped, plan = side_rows(manifest, splits={'train','val'})
    if not plan['ready_for_training']:
        raise ValueError('면별 학습/모델선택 자료 부족: '+str(plan['issues']))
    device = device_for(device)
    torch.manual_seed(42)
    backbone, dimension = backbone_for(backbone_name, pretrained)
    backbone = backbone.to(device)
    started = time.perf_counter()
    if fine_tune_last:
        # Cache the frozen prefix; only the final convolution and head get gradients.
        last = backbone[-1].requires_grad_(True)
        with torch.no_grad():
            early_features = torch.stack([backbone[:-1](side_views(r['image'],r['box'],crop,tiles).to(device)) for r in rows]).detach()
    else:
        with torch.inference_mode():
            features = torch.cat([backbone(side_views(r['image'],r['box'],crop,tiles).to(device)).mean((2,3)).flatten().unsqueeze(0).cpu() for r in rows])
        features = features.clone().to(device)
    labels = torch.tensor([[r['labels'][k] if r['labels'][k] is not None else -1 for k in LABELS] for r in rows],dtype=torch.float32,device=device)
    indices = {s:torch.tensor([i for i,r in enumerate(rows) if r['split']==s],device=device) for s in ('train','val')}
    train_counts, ratios = training_balance(rows, plan['supported'])
    pos_weight = torch.tensor(ratios if balance else [1.0]*len(LABELS), device=device)
    active = torch.tensor([k in plan['supported'] for k in LABELS],device=device)
    torch.manual_seed(42)
    head = nn.Linear(dimension*(5 if tiles else 1),len(LABELS)).to(device)
    optimizer = torch.optim.AdamW([{'params':head.parameters(),'lr':.001},
                                   {'params':last.parameters(),'lr':.0001}] if fine_tune_last else head.parameters(),lr=.001)
    def selected_features(ix):
        if not fine_tune_last:
            return features[ix]
        maps = last(early_features[ix].flatten(0,1))
        return maps.mean((2,3)).reshape(len(ix),-1)
    history, best, best_state = [], float('inf'), None
    best_last_state = None
    selected_epoch = None
    for epoch in range(epochs):
        stats={'epoch':epoch+1}
        for phase in ('train','val'):
            ix=indices[phase]; mask=(labels[ix]>=0)&active
            with torch.set_grad_enabled(phase=='train'):
                logits=head(selected_features(ix))
                if phase=='train' and balance:
                    losses=nn.functional.binary_cross_entropy_with_logits(logits,labels[ix].clamp_min(0),pos_weight=pos_weight,reduction='none')
                    loss=losses[mask].mean()
                else:
                    loss=nn.functional.binary_cross_entropy_with_logits(logits[mask],labels[ix][mask])
                if not torch.isfinite(loss): raise ValueError('Non-finite loss')
                if phase=='train':
                    optimizer.zero_grad();loss.backward();optimizer.step()
            stats[phase]=loss.item()
        history.append(stats)
        if stats['val']<best:
            selected_epoch=epoch+1
            best=stats['val'];best_state={k:v.detach().cpu().clone() for k,v in head.state_dict().items()}
            if fine_tune_last:
                best_last_state={k:v.detach().cpu().clone() for k,v in last.state_dict().items()}
    head.load_state_dict(best_state)
    if fine_tune_last:
        last.load_state_dict(best_last_state)
    with torch.inference_mode(): probabilities=head(selected_features(indices['val'])).sigmoid().cpu().tolist()
    validation_rows=[r for r in rows if r['split']=='val']
    metrics,predictions=score(validation_rows,probabilities,plan['supported'])
    with torch.inference_mode():
        train_probabilities=head(selected_features(indices['train'])).sigmoid().cpu().tolist()
    train_metrics,_=score([r for r in rows if r['split']=='train'],train_probabilities,plan['supported'])
    report={'backbone_name':backbone_name,'selected_epoch':selected_epoch,'best_validation_loss':best,'training_metrics':train_metrics,'evaluation_kind':'validation','final_performance_claim':False,'seed':42,'epochs':epochs,'image_size':224,'pretrained':pretrained,'mode':'tiles' if tiles else ('crop' if crop else 'full'),'views':5 if tiles else 1,'feature_dim':dimension*(5 if tiles else 1),'fine_tune_last':fine_tune_last,'counts':{s:len(i) for s,i in indices.items()},
            'balance':balance,'train_label_counts':train_counts,'positive_weights':dict(zip(LABELS,pos_weight.cpu().tolist())),
            'selection_metric':'unweighted validation BCE','supported':plan['supported'],'skipped':skipped,'history':history,'metrics':metrics,
            **visibility_report(rows, probabilities, plan['supported']),
            'predictions':predictions,'elapsed_seconds':time.perf_counter()-started,'device':str(device),
            'manifest_sha256':hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
            'requires_gemini':True,'production_ready':False,'actual_calls_saved':0}
    output.mkdir(parents=True,exist_ok=False)
    torch.save({'architecture':backbone_name+'_single_side_v1','backbone_name':backbone_name,'backbone':{k:v.cpu() for k,v in backbone.state_dict().items()},
                'selected_epoch':selected_epoch,'best_validation_loss':best,'balance':balance,'positive_weights':report['positive_weights'],'head':best_state,'crop':crop,'tiles':tiles,'labels':list(LABELS),'supported':plan['supported'],
                'manifest_sha256':report['manifest_sha256'],'training_groups':sorted({r['group'] for r in rows if r['split']!='test'}),
                'development_ids':sorted({r['card_id'] for r in rows}),
                'development_image_hashes':sorted({h for r in rows for h in r['_image_hashes']}),
                'pretrained':pretrained,'fine_tune_last':fine_tune_last,'status':'experimental'},output/'model.pt')
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report
