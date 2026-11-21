"""Fit and evaluate one unchanged fold with the confirmed-normal print term."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageOps
import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('print_head', Path(__file__).with_name('head.py'))
head = importlib.util.module_from_spec(spec)
spec.loader.exec_module(head)
source = ROOT / 'tools/experiments/corner-card-ranking-20261121/worker.py'
spec = importlib.util.spec_from_file_location('rank_worker', source)
rank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rank)


def print_tokens(row, box):
    with Image.open(row['image']) as image:
        w,h = ImageOps.exif_transpose(image).size
    x,y,u,v = row['box']
    l,t = math.floor(x*w),math.floor(y*h)
    cw,ch = math.ceil(u*w)-l,math.ceil(v*h)-t
    rw,rh = ImageOps.contain(Image.new('L',(cw,ch)),(448,448)).size
    pl,pt = round((448-rw)/2),round((448-rh)/2)
    a,b,c,d = box
    x0,x1 = pl+(a*w-l)*rw/cw,pl+(c*w-l)*rw/cw
    y0,y1 = pt+(b*h-t)*rh/ch,pt+(d*h-t)*rh/ch
    edges = torch.arange(32)*14
    return (((edges >= y0) & (edges+14 <= y1))[:,None]
            & ((edges >= x0) & (edges+14 <= x1))[None,:]).flatten()


def samples(grid, boxes):
    return [float(grid[a:c+1,b:d+1].amax()) for a,b,c,d in boxes]


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    for name in ('worker.py','head.py'):
        if Path(__file__).with_name(name).read_bytes() != (ROOT/plan['tracked_directory']/name).read_bytes():
            raise ValueError('Mirror differs: ' + name)
    for file, expected in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen input differs: ' + file)
    archive = json.loads((ROOT/plan['replayed_observations']).read_text())
    prior = json.loads((ROOT/plan['original_plan']).read_text())
    rows = archive['rows']
    folds = rank.cv.fold_of(rows)
    f = plan['fold']
    train = [i for i,r in enumerate(rows) if folds[r['group']] != f]
    test = [i for i,r in enumerate(rows) if folds[r['group']] == f]
    learning, checked = [rows[i] for i in train], [rows[i] for i in test]
    if checked != ref['rows'] or [archive['scores'][i] for i in test] != ref['before_scores']:
        raise ValueError('Frozen evaluation mismatch')
    separation = rank.sw.check_separation(learning,checked)
    reg = {p['id']:p['box'] for p in json.loads((ROOT/plan['training_regions']).read_text())}
    learn_ids = {r['id'] for r in learning if r['target']}
    if reg.keys() - learn_ids or len(reg)!=49:
        raise ValueError('Confirmed normal print crosses training boundary')
    supervision = torch.stack([print_tokens(r,reg[r['id']]) if r['id'] in reg
                               else torch.zeros(1024,dtype=torch.bool) for r in learning])
    if int(supervision.any(1).sum())!=len(reg):
        raise ValueError('Confirmed print must contain at least one full patch')
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    body = torch.hub.load(str(ROOT/prior['backbone_directory']),'dinov2_vits14',source='local',pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/prior['backbone_weights'],map_location='cpu',weights_only=True))
    print(f'Extracting features. Held-out: {len(checked)} zones. Confirmed print: {len(reg)} zones.',flush=True)
    x,m = rank.sw.features(body.to('mps'),rows,'mps')
    t,h = torch.tensor(train),torch.tensor(test)
    if bool((supervision & ~m[t]).any()):
        raise ValueError('Confirmed print must be inside valid mask')
    saved = torch.load(ROOT/plan['replayed_heads'],map_location='cpu',weights_only=True)[f]
    old = rank.sw.score(x[h],m[h],saved['coef'],saved['bias'])
    delta = max(abs(a-b) for a,b in zip(old,ref['before_scores'],strict=True))
    if delta>2e-6:
        raise ValueError('Stored control did not replay')
    print('Fitting one model with the confirmed-print penalty.',flush=True)
    coef,bias,convergence = head.fit(x[t],m[t],learning,prior['card_pair_weight'],supervision,plan['weight'])
    scores = rank.sw.score(x[h],m[h],coef,bias)
    target = next(i for i in test if rows[i]['id']==plan['sample_id'])
    maps = [(x[target]@w+b).sigmoid().masked_fill(~m[target],-1).view(32,32)
            for w,b in ((saved['coef'],saved['bias']),(coef,bias))]
    values = [dict(green=samples(g,plan['green']),whitening=samples(g,plan['whitening']),
                   map=g.tolist()) for g in maps]
    a,b = [dict(miss=head.frozen.template.card_miss(checked,s,0,fixed=prior['fixed_low'])['miss'],
                false_alarm=head.frozen.template.card_miss(checked,s,0,fixed=prior['fixed_high'])['false_alarm'],
                auc=rank.bag.auc(checked,s)) for s in (old,scores)]
    green_drop = sum(values[0]['green'])/4 - sum(values[1]['green'])/4
    criteria = dict(lower_print=green_drop>=plan['min_normal_drop'],
                    preserve_whitening=all(p-q<=plan['max_defect_drop']
                                           for p,q in zip(values[0]['whitening'],values[1]['whitening'],strict=True)),
                    no_card_regression=b['miss']<=a['miss'] and b['false_alarm']<=a['false_alarm'])
    evidence = dict(control=a,candidate=b,green_drop=green_drop,separation=separation,
                    max_control_delta=delta,convergence=convergence,criterion=criteria,
                    criterion_met=all(criteria.values()),normal_regions=len(reg),
                    normal_patches=int(supervision.sum()),training_calls=1,external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(evidence,allow_nan=False,indent=2))
    (out/'case94.json').write_text(json.dumps(values,allow_nan=False,indent=2))
    (out/'observations.json').write_text(json.dumps(dict(rows=checked,scores=scores),allow_nan=False))
    print(json.dumps(evidence),flush=True)


if __name__ == '__main__':
    run()
