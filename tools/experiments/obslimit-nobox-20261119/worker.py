"""H1 (2026-11-19): does candidate F depend on the human-confirmed card box? Same 267 dev rows, same photo-group 5-fold, same v1.8 recipe (DINOv2 vits14 448 patch-mean + standardized L2 logistic). Control arm = human box (must reproduce the reference OOF scores); treatment arm = whole EXIF-rotated photo ([0,0,1,1]). Single changed variable: crop source. Development CV only, not independent. Common-runner only."""
import hashlib
import importlib.util
import json
import math
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
HYPOTHESIS = 'obslimit-nobox-20261119'
WHOLE = [0., 0., 1., 1.]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ps = _load('obspooled', 'artifacts/obslimit-pooled-source-20261103/worker.py')
ms, bag, sw, cv = ps.ms, ps.bag, ps.sw, ps.cv


def pooled(body, rows, device):
    x, m = sw.features(body, rows, device)
    return (x*m[..., None]).sum(1)/m.sum(1, keepdim=True)


def wilson(k, n, z=1.96):
    p, d = k/n, 1+z*z/n
    c, h = (p+z*z/(2*n))/d, z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [c-h, c+h]


def counts(rows, scores):
    fn = sum(1 for r, s in zip(rows, scores) if r['target'] == 1 and s < .5)
    fp = sum(1 for r, s in zip(rows, scores) if r['target'] == 0 and s >= .5)
    pos = sum(r['target'] for r in rows)
    neg = len(rows)-pos
    return dict(fn=fn, positives=pos, miss_rate=fn/pos, miss_wilson=wilson(fn, pos),
                fp=fp, negatives=neg, fp_rate=fp/neg, fp_wilson=wilson(fp, neg))


def check_inputs(plan, ref):
    if plan['hypothesis_id'] != HYPOTHESIS:
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    return rows


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    rows = check_inputs(plan, ref)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    fold = cv.fold_of(rows)
    control = ps.oof(pooled(body, rows, device), rows, fold)
    drift = max(abs(a-b) for a, b in zip(control, ref['before_scores']))
    if drift > plan['control_reproduction_tolerance']:
        raise ValueError(f'Control arm does not reproduce reference scores (max diff {drift:.6f})')
    treat = ps.oof(pooled(body, [dict(r, box=WHOLE) for r in rows], device), rows, fold)
    auc_c, auc_t = bag.auc(rows, control), bag.auc(rows, treat)
    delta = ps.paired(rows, control, treat)
    crit = plan['criterion']
    criterion = dict(delta_point=auc_t-auc_c >= crit['min_delta_auc'], delta_lower=delta['lo'] >= crit['min_delta_auc_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=treat), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, verdict='box_not_bottleneck' if all(criterion.values()) else 'box_needed',
                   control=dict(auc=auc_c, bootstrap=ms.auc_ci(rows, control), **counts(rows, control), reproduction_max_diff=drift),
                   treatment=dict(auc=auc_t, bootstrap=ms.auc_ci(rows, treat), **counts(rows, treat)),
                   delta_auc=auc_t-auc_c, delta_bootstrap=delta, control_scores=control, rows=len(rows), device=device,
                   training_calls=2*cv.FOLDS, external_ai_calls=0, independent=False)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'control_scores'}, ensure_ascii=False, default=float), flush=True)
