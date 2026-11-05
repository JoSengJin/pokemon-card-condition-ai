"""Within-photo pair term vs the control recipe on manifest 20261031m (k+l units): full-data heads and 20 group-bootstrap heads per arm, same seeds. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pb = _load('pbag', 'tools/experiments/edge-back-pair-bagging-20261031/worker.py')
pair, bag, sw = pb.pair, pb.bag, pb.sw


def control_heads(xt, mt, train, xv, mv):
    """Same seeds and redraw rule as bag.bag_scores (control recipe without the pair term)."""
    return bag.bag_scores(xt, mt, train, xv, mv)


def spread(val, heads):
    single = [bag.auc(val, h) for h in heads]
    mean = sum(single)/len(single)
    same = [bag.auc(val, h, True) for h in heads]
    return dict(mean=mean, std=(sum((a - mean)**2 for a in single)/(len(single) - 1))**.5, min=min(single), max=max(single),
                below_half=sum(a < .5 for a in single), same_photo_mean=sum(same)/len(same))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-pair-vs-control-m-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'val']
    if [len(train), len(val)] != plan['expected_denominators']['train_val'] or [dict(r) for r in val] != ref['rows']:
        raise ValueError('Frozen denominator or reference rows changed')
    separation = sw.check_separation(train, val)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = sw.features(body, train, device)
    xv, mv = sw.features(body, val, device)
    c_coef, c_bias, _ = sw.fit(xt, mt, train)
    p_coef, p_bias, p_conv = pair.fit_pair(xt, mt, train)
    c_full, p_full = sw.score(xv, mv, c_coef, c_bias), sw.score(xv, mv, p_coef, p_bias)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=p_full), allow_nan=False))
    c_heads, c_redraws = control_heads(xt, mt, train, xv, mv)
    p_heads, p_redraws = pb.pair_heads(xt, mt, train, xv, mv)
    c, p = spread(val, c_heads), spread(val, p_heads)
    delta = p['mean'] - c['mean']
    summary = dict(delta_mean_auc=delta, criterion_min_delta=plan['criterion_min_delta'], criterion_met=delta >= plan['criterion_min_delta'],
                   control_bootstrap=c, pair_bootstrap=p, control_full=dict(auc=bag.auc(val, c_full), same_photo=bag.auc(val, c_full, True),
                   fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, c_full)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, c_full))),
                   pair_full=dict(auc=bag.auc(val, p_full), same_photo=bag.auc(val, p_full, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, p_full)),
                   fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, p_full))), head3_auc=bag.auc(val, ref['before_scores']), val_positive=sum(r['target'] for r in val),
                   val_normal=sum(1 - r['target'] for r in val), redraws=dict(control=c_redraws, pair=p_redraws), pair_convergence=p_conv, train_units=len(train),
                   device=device, separation=separation, typed_point_response='not_evaluated', training_calls=2 + 2*bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
