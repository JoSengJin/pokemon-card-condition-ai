"""Experimental observation-limit classifier; never a condition or bypass decision."""
from collections import Counter
import json
import math
from pathlib import Path

import torch
from torch import nn

from .data import load_manifest
from .model import checked_sigmoid, device_for
from .point_probe import digest
from .regions import validate_annotations
from .score_diagnostics import score_diagnostics
from .edge_views import patch_features
from .side_model import backbone_for
from .observation_backbone import BACKBONES, DINOV2_REVISION, dino_backbone
from .observation_signals import local_color_texture
from .observation_scaling import fit_scaling, apply_scaling, validate_scaling
from .side_experiment import side_image

TARGET = 'observation_limited'


def visibility_rows(manifest, splits=None):
    rows, skipped = [], []
    for record in load_manifest(manifest, splits={'train', 'val'} if splits is None else splits, require_gradable=False):
        if record.get('excluded'):
            continue
        annotations = validate_annotations(record.get('side_annotations', {}), record)
        for side in ('front', 'back'):
            a = annotations.get(side)
            issues = a.get('visibility_issues') if a else None
            target = 1 if issues else 0 if issues == [] and a['labels']['gradable'] == 1 else None
            if not a or a['box'] is None or target is None:
                skipped.append(dict(card_id=record['id'], side=side,
                    reason='missing_annotation_or_box' if not a or a['box'] is None else 'unknown_observation_truth'))
                continue
            rows.append(dict(card_id=record['id'], group=record['group'], split=record['split'],
                side=side, image=record[side], box=a['box'], visibility_issues=issues,
                labels={TARGET: target}, image_hashes=record['_image_hashes']))
    return rows, skipped


def class_group_weights(rows):
    counts = Counter((r['labels'][TARGET], r['group']) for r in rows)
    groups = Counter(label for label, group in counts)
    if set(groups) != {0, 1}:
        raise ValueError('Both observation-limited and explicitly clear examples are required in train and val')
    return [1 / (counts[r['labels'][TARGET], r['group']] * groups[r['labels'][TARGET]]) for r in rows]


def fit_centroid(head, features, labels, weights):
    """Train-only weighted means; squared-distance difference in mean feature units."""
    with torch.no_grad():
        means = [(features[labels == value] * weights[labels == value, None]).sum(0)
                 / weights[labels == value].sum() for value in (0, 1)]
        dimension = features.shape[1]
        head.weight.copy_((2 * (means[1] - means[0]) / dimension).unsqueeze(0))
        head.bias.copy_(((means[0].square().sum() - means[1].square().sum()) / dimension).reshape(1))


def fit_side_centroids(head, features, rows):
    for number, side in enumerate(('front','back')):
        selected=[i for i,r in enumerate(rows) if r['side']==side]
        part=[rows[i] for i in selected]
        weights=features.new_tensor(class_group_weights(part))
        labels=features.new_tensor([r['labels'][TARGET] for r in part])
        local=nn.Linear(features.shape[1],1).to(features.device)
        fit_centroid(local,features[selected],labels,weights)
        with torch.no_grad():
            head.weight[number].copy_(local.weight[0])
            head.bias[number].copy_(local.bias[0])


def observation_logits(head, features, sides):
    values=head(features)
    return values.gather(1,sides[:,None]).squeeze(1) if head.out_features==2 else values.squeeze(1)


def side_diagnostics(predictions, training):
    result={}
    for side in ('front','back'):
        part=[r for r in predictions if r['side']==side]
        train=[r for r in training if r['side']==side]
        metrics=dict(tp=0,tn=0,fp=0,fn=0)
        for row in part:
            truth=row['labels'][TARGET]; guess=int(row['probabilities'][TARGET]>=.5)
            metrics[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
        ranking=score_diagnostics(part,[TARGET])[TARGET] if part else None
        result[side]=dict(train_faces=len(train),train_groups=len({r['group'] for r in train}),
            train_clear=sum(r['labels'][TARGET]==0 for r in train),train_limited=sum(r['labels'][TARGET]==1 for r in train),
            validation_faces=len(part),validation_groups=len({r['group'] for r in part}),metrics_at_05=metrics,
            ranking={k:ranking[k] for k in ('known','positive','negative','groups','auroc','average_precision','balanced_accuracy_at_05')} if ranking else None,
            warning='missing_validation_class' if len({r['labels'][TARGET] for r in part})<2 else None)
    return result


def observation_features(backbone, row, device, tiles=False, interior=False, local_signals=False):
    if interior:
        left, top, right, bottom = row['box']
        dx, dy = (right-left)*.05, (bottom-top)*.05
        row = dict(row, box=[left+dx,top+dy,right-dx,bottom-dy])
    features=patch_features(backbone,row,device,'tiles' if tiles else False)
    if local_signals:
        extra=torch.tensor(local_color_texture(side_image(row['image'],row['box'],True,224)),device=device,dtype=features.dtype).unsqueeze(0)
        features=torch.cat((features,extra),dim=1)
    return features


def reason_diagnostics(predictions, training):
    from .regions import VISIBILITY_ISSUES
    result = {}
    for reason in VISIBILITY_ISSUES:
        train = [r for r in training if reason in r['visibility_issues']]
        val = [r for r in predictions if reason in r['visibility_issues']]
        detected = sum(r['probabilities'][TARGET] >= .5 for r in val)
        result[reason] = dict(train_faces=len(train),train_groups=len({r['group'] for r in train}),
            validation_faces=len(val),validation_groups=len({r['group'] for r in val}),
            detected=detected,missed=len(val)-detected,
            recall=detected/len(val) if val else None,
            warning='no_training_support' if val and not train else 'no_validation_support' if not val else None)
    return result


def experiment(manifest, output, epochs=20, device='auto', pretrained=True, tiles=False, centroid=False, interior=False, backbone_name='mobilenet_v3_small', local_signals=False, standardize=False, side_aware=False):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new experiment directory')
    if type(side_aware) is not bool:
        raise ValueError('side_aware must be boolean')
    if side_aware and (not centroid or local_signals or standardize or tiles or interior or backbone_name!='mobilenet_v3_small'):
        raise ValueError('Side-aware centroids require unchanged MobileNet context input')
    if type(standardize) is not bool:
        raise ValueError('standardize must be boolean')
    if standardize and not local_signals:
        raise ValueError('Standardization requires local signals centroid experiment')
    if type(local_signals) is not bool:
        raise ValueError('local_signals must be boolean')
    if local_signals and (backbone_name != 'mobilenet_v3_small' or not centroid or tiles or interior):
        raise ValueError('Local signals require MobileNet centroid with unchanged context input')
    if type(interior) is not bool:
        raise ValueError('interior must be boolean')
    if type(centroid) is not bool:
        raise ValueError('centroid must be boolean')
    if type(tiles) is not bool:
        raise ValueError('tiles must be boolean')
    if type(epochs) is not int or epochs < 1:
        raise ValueError('epochs must be positive')
    if backbone_name not in BACKBONES:
        raise ValueError('Unsupported observation backbone')
    if backbone_name == 'dinov2_vits14' and (not centroid or tiles or interior):
        raise ValueError('DINOv2 experiment requires centroid with unchanged context input')
    before = {str(Path(manifest).resolve()): digest(manifest)}
    rows, skipped = visibility_rows(manifest)
    phases = {s: [r for r in rows if r['split'] == s] for s in ('train', 'val')}
    weights = {s: class_group_weights(part) for s, part in phases.items()}
    for row in rows:
        before[row['image']] = digest(row['image'])
    device = device_for(device)
    torch.manual_seed(42)
    backbone, dimension = dino_backbone(pretrained) if backbone_name == 'dinov2_vits14' else backbone_for(backbone_name, pretrained)
    backbone.to(device)
    with torch.inference_mode():
        features = torch.cat([observation_features(backbone, r, device, tiles, interior, local_signals).cpu()
                              for r in rows])
    features = features.clone().to(device)
    labels = torch.tensor([r['labels'][TARGET] for r in rows], dtype=torch.float32, device=device)
    indices = {s: torch.tensor([i for i, r in enumerate(rows) if r['split'] == s], device=device)
               for s in phases}
    sides=torch.tensor([int(r['side']=='back') for r in rows],device=device)
    weights = {s: torch.tensor(w, device=device) for s, w in weights.items()}
    scaling=fit_scaling(features[indices['train']], [r['group'] for r in phases['train']]) if standardize else None
    features=apply_scaling(features,scaling)
    torch.manual_seed(42)
    head = nn.Linear(dimension * (2 if tiles else 1) + (36 if local_signals else 0), 2 if side_aware else 1).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=.001) if not centroid else None
    if centroid:
        ix = indices['train']
        if side_aware:
            fit_side_centroids(head,features[ix],phases['train'])
        else:
            fit_centroid(head, features[ix], labels[ix], weights['train'])
    history, best, best_state, selected_epoch = [], float('inf'), None, None
    for epoch in range(1 if centroid else epochs):
        stats = dict(epoch=epoch+1)
        for phase, ix in indices.items():
            with torch.set_grad_enabled(phase == 'train' and not centroid):
                logits = observation_logits(head,features[ix],sides[ix])
                losses = nn.functional.binary_cross_entropy_with_logits(logits, labels[ix], reduction='none')
                loss = (losses * weights[phase]).sum() / weights[phase].sum()
                if not torch.isfinite(loss):
                    raise ValueError('Non-finite observation loss; no checkpoint saved')
                if phase == 'train' and not centroid:
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
            stats[phase] = loss.item()
        history.append(stats)
        if stats['val'] < best:
            best, selected_epoch = stats['val'], epoch+1
            best_state = {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}
    head.load_state_dict(best_state)
    with torch.inference_mode():
        values = observation_logits(head,features[indices['val']],sides[indices['val']]).sigmoid().cpu().tolist()
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite observation score; no checkpoint saved')
    predictions = [dict(**row, probabilities={TARGET: value}) for row, value in zip(phases['val'], values)]
    metrics = dict(tp=0, tn=0, fp=0, fn=0)
    for row, value in zip(phases['val'], values):
        truth, guess = row['labels'][TARGET], int(value >= .5)
        metrics[('t' if truth == guess else 'f') + ('p' if guess else 'n')] += 1
    if any(digest(path) != sha for path, sha in before.items()):
        raise ValueError('Observation inputs changed; no checkpoint saved')
    counts = {s: dict(faces=len(part), physical_groups=len({r['group'] for r in part}),
        clear_faces=sum(r['labels'][TARGET] == 0 for r in part),
        limited_faces=sum(r['labels'][TARGET] == 1 for r in part),
        reasons=dict(Counter(reason for r in part for reason in r['visibility_issues']))) for s, part in phases.items()}
    report = dict(evaluation_kind='validation_observation_limit', target=TARGET,
        backbone_name=backbone_name, feature_dimension=dimension, local_signals=local_signals,
        input_feature_dimension=features.shape[1],
        feature_scaling='train_group_standard_v1' if standardize else 'none',
        scaling_fit_faces=len(phases['train']) if standardize else 0,
        scaling_fit_groups=sorted({r['group'] for r in phases['train']}) if standardize else [],
        backbone_revision=DINOV2_REVISION if backbone_name == 'dinov2_vits14' else None,
        target_definition='1: explicit observation reason; 0: explicit empty reasons AND side gradable=1; otherwise unknown',
        counts=counts, skipped=skipped, epochs=0 if centroid else epochs, seed=42, pretrained=pretrained,
        head_policy='train_side_weighted_centroid' if side_aware else 'train_weighted_centroid' if centroid else 'adamw_linear',
        input_policy='tiles' if tiles else 'context', views=5 if tiles else 1,
        preprocessing='interior90' if interior else 'box',
        side_aware=side_aware, side_diagnostics=side_diagnostics(predictions,phases['train']),
        reason_diagnostics=reason_diagnostics(predictions,phases['train']),
        selected_epoch=None if centroid else selected_epoch, history=history, metrics=metrics,
        diagnostics=score_diagnostics(predictions, [TARGET]), predictions=predictions,
        input_hashes=before, image_size=224, device=str(device),
        selection_metric='none: train-only weighted centroids' if centroid else 'class then physical-group balanced validation BCE',
        production_ready=False, requires_gemini=True, actual_calls_saved=0,
        limitations=['Uncalibrated observation score; not a condition grade, clean-card label or bypass decision.',
            'Human card boxes required. No localization or individual reason classification.',
            'Clear means no recorded observation restriction on a gradable face, not no card defects.',
            'Reused validation; source reasons may be incomplete. No independent final performance claim.',
            'Diagnostic normal/defect terms refer only to observation target 0/1.',
            'A low score never establishes full visibility and must not remove human restrictions.'])
    from .visibility_compare import quality_summary
    report['quality_check'] = quality_summary(report)
    output.mkdir(parents=True, exist_ok=False)
    torch.save(dict(architecture=backbone_name+'_visibility_v1', target=TARGET, image_size=224,
        local_signals=local_signals, feature_scaling=scaling, side_aware=side_aware,
        backbone_name=backbone_name, backbone_revision=DINOV2_REVISION if backbone_name == 'dinov2_vits14' else None,
        backbone={k: v.cpu() for k, v in backbone.state_dict().items()}, head=best_state,
        input_policy='tiles' if tiles else 'context',
        preprocessing='interior90' if interior else 'box',
        development_ids=sorted({r['card_id'] for r in rows}),
        development_groups=sorted({r['group'] for r in rows}),
        development_image_hashes=sorted({h for r in rows for h in r['image_hashes']}),
        manifest_sha256=before[str(Path(manifest).resolve())], selected_epoch=None if centroid else selected_epoch,
        head_policy='train_side_weighted_centroid' if side_aware else 'train_weighted_centroid' if centroid else 'adamw_linear',
        status='experimental'), output/'model.pt')
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return report


class VisibilityAnalyzer:
    def __init__(self, checkpoint, device='auto'):
        self.device = device_for(device)
        meta = torch.load(checkpoint, map_location='cpu', weights_only=True)
        name = meta.get('backbone_name', 'mobilenet_v3_small') if isinstance(meta, dict) else None
        if (not isinstance(meta, dict) or name not in BACKBONES or meta.get('architecture') != name+'_visibility_v1'
                or meta.get('target') != TARGET or type(meta.get('image_size')) is not int
                or meta['image_size'] != 224 or meta.get('input_policy', 'context') not in ('context', 'tiles')
                or meta.get('preprocessing','box') not in ('box','interior90')
                or not {'backbone', 'head'} <= set(meta)):
            raise ValueError('Unsupported observation checkpoint')
        if name == 'dinov2_vits14' and (meta.get('backbone_revision') != DINOV2_REVISION
                or meta.get('input_policy') != 'context' or meta.get('preprocessing') != 'box'
                or meta.get('head_policy') != 'train_weighted_centroid'):
            raise ValueError('Unsupported DINOv2 observation checkpoint')
        self.supported_sides=meta.get('supported_sides')
        if self.supported_sides is not None and (
                type(self.supported_sides) is not list or not self.supported_sides
                or any(s not in ('front','back') for s in self.supported_sides)
                or len(set(self.supported_sides))!=len(self.supported_sides)):
            raise ValueError('Unsupported observation side scope')
        self.local_signals=meta.get('local_signals',False)
        if type(self.local_signals) is not bool or self.local_signals and (
                name != 'mobilenet_v3_small' or meta.get('input_policy') != 'context'
                or meta.get('preprocessing') != 'box' or meta.get('head_policy') != 'train_weighted_centroid'):
            raise ValueError('Unsupported local observation signals checkpoint')
        self.side_aware=meta.get('side_aware',False)
        if type(self.side_aware) is not bool or self.side_aware and (
                name!='mobilenet_v3_small' or self.local_signals or meta.get('feature_scaling') is not None
                or meta.get('input_policy')!='context' or meta.get('preprocessing')!='box'
                or meta.get('head_policy')!='train_side_weighted_centroid'):
            raise ValueError('Unsupported side-aware observation checkpoint')
        self.scaling=meta.get('feature_scaling')
        if self.scaling is not None:
            if not self.local_signals:
                raise ValueError('Unsupported observation scaling without local signals')
            validate_scaling(self.scaling,612)
        self.backbone, dimension = dino_backbone() if name == 'dinov2_vits14' else backbone_for(name)
        self.backbone.to(self.device).load_state_dict(meta['backbone'], strict=True)
        self.policy = meta.get('input_policy', 'context')
        self.interior = meta.get('preprocessing','box') == 'interior90'
        self.head = nn.Linear(dimension * (2 if self.policy == 'tiles' else 1) + (36 if self.local_signals else 0), 2 if self.side_aware else 1).to(self.device).eval()
        self.head.load_state_dict(meta['head'], strict=True)
        self.model_sha256 = digest(checkpoint)

    def analyze(self, image, box, side=None):
        if self.supported_sides is not None and side not in self.supported_sides:
            raise ValueError('Explicit supported observation side required; use fallback')
        if self.side_aware and side not in ('front','back'):
            raise ValueError('Side-aware checkpoint requires explicit front/back side; use fallback')
        from .regions import region_box
        region_box(box, 'center')  # Validate the full-card coordinates without selecting a center crop.
        with torch.inference_mode():
            features=observation_features(self.backbone, dict(image=image, box=box), self.device,
                                          self.policy == 'tiles', self.interior, self.local_signals)
            sides=torch.tensor([int(side=='back')],device=self.device)
            value = checked_sigmoid(observation_logits(self.head,apply_scaling(features,self.scaling),sides)).item()
        if not math.isfinite(value):
            raise ValueError('Non-finite observation output; use fallback')
        return dict(observation_limit_score=value, model_sha256=self.model_sha256,
            requires_gemini=True, production_ready=False, actual_calls_saved=0,
            decision='review_required',
            limitations=['Uncalibrated observation signal only; cannot confirm clear visibility or card condition.',
                         'Human observation restrictions must be retained regardless of this score.',
                         'interior90 discards outer pixels: sensitivity experiment, not a full-card visibility check.'])
