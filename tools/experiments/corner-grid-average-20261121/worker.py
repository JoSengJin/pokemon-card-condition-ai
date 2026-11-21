"""Test a fixed four-phase grid average with unchanged OOF corner heads."""
from collections import defaultdict
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
source = ROOT / 'tools/experiments/corner-card-ranking-20261121/worker.py'
spec = importlib.util.spec_from_file_location('rank_worker', source)
rank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rank)
PHASES = [(0,0),(7,0),(0,7),(7,7)]


def moved_input(tensor, mask, dx, dy):
    gray = tensor.new_tensor([(128/255-m)/s for m,s in zip((.485,.456,.406),(.229,.224,.225),strict=True)])
    moved = gray[:,None,None].expand_as(tensor).clone()
    moved[:,dy:,dx:] = tensor[:,:448-dy,:448-dx]
    valid = torch.zeros_like(mask)
    valid[dy:,dx:] = mask[:448-dy,:448-dx]
    return moved,valid


def phase_scores(body, tensor, mask, head):
    scores = []
    with torch.inference_mode():
        for dx,dy in PHASES:
            image, real = moved_input(tensor,mask,dx,dy)
            valid = real.reshape(32,14,32,14).any(3).any(1).flatten()
            z = body.forward_features(image[None].to('mps'))['x_norm_patchtokens'].cpu()[0]
            logits = (z@head['coef']+head['bias']).masked_fill(~valid,-torch.inf)
            scores.append(float(logits.amax().sigmoid()))
    return scores


def missed_cards(rows, values, floor):
    best = {}
    for row,s in zip(rows,values,strict=True):
        if row['target']:
            g=row['group']
            best[g]=max(best.get(g,0.),s)
    return {g for g,s in best.items() if s<floor}


def run():
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text())
    ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror mismatch')
    for path,h in plan['input_sha256'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest()!=h:
            raise ValueError('Frozen input differs: '+path)
    replay=json.loads((ROOT/plan['replayed_observations']).read_text())
    e=json.loads((ROOT/plan['e_observations']).read_text())
    prior=json.loads((ROOT/plan['original_plan']).read_text())
    keep=[i for i,r in enumerate(replay['rows']) if r['group']!=plan['excluded_group']]
    rows,old=ref['rows'],ref['before_scores']
    if rows!=[replay['rows'][i] for i in keep] or old!=[replay['scores'][i] for i in keep] or e['rows']!=replay['rows']:
        raise ValueError('Reference or exclusion differs')
    rank.sw.check_separation([],rows)
    folds=rank.cv.fold_of(replay['rows'])
    heads=torch.load(ROOT/plan['replayed_heads'],map_location='cpu',weights_only=True)
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    body=torch.hub.load(str(ROOT/prior['backbone_directory']),'dinov2_vits14',source='local',pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/prior['backbone_weights'],map_location='cpu',weights_only=True))
    body=body.to('mps')
    by_image=defaultdict(list)
    for i,r in enumerate(rows):
        by_image[r['image']].append(i)
    values=[None]*len(rows)
    for n,(image,inds) in enumerate(by_image.items(),1):
        boxes=[rows[i]['box'] for i in inds]
        for i,t in zip(inds,rank.sw.view_tensors(image,boxes,448),strict=True):
            mask=rank.sw.physical_pixel_mask(image,rows[i]['box'],halo=0,image_size=448)
            values[i]=phase_scores(body,t,mask,heads[folds[rows[i]['group']]])
        if n%50==0:
            print(f'Completed {n}/{len(by_image)} photos',flush=True)
    delta=max(abs(v[0]-s) for v,s in zip(values,old,strict=True))
    if delta>2e-6:
        raise ValueError(f'Unshifted replay differs: {delta:.8g}')
    candidate=[sum(v)/len(PHASES) for v in values]
    a,b,e_ref=[rank.summarize(rows,s,prior) for s in (old,candidate,[e['scores'][i] for i in keep])]
    misses=missed_cards(rows,candidate,prior['fixed_low'])-missed_cards(rows,old,prior['fixed_low'])
    criterion=dict(fp_drop=a['fixed_fp']-b['fixed_fp']>=plan['min_fp_drop'],
                   no_new_misses=not misses,
                   matched_miss=b['matched']['miss']<=a['matched']['miss'],
                   within_photo=b['same_photo_auc']>=a['same_photo_auc']-plan['max_within_auc_drop'])
    report=dict(control=a,candidate=b,e_reference=e_ref,criterion=criterion,criterion_met=all(criterion.values()),
                replay_delta=delta, new_missed_cards=sorted(misses),phases=PHASES,training_calls=0,external_ai_calls=0)
    (out/'phase-scores.json').write_text(json.dumps(values,allow_nan=False))
    (out/'evaluation.json').write_text(json.dumps(report,allow_nan=False,indent=2))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows,scores=candidate),allow_nan=False))
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    run()
