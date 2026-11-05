"""Zoomed back-corner input: same recipe (ViT-S/14 448 tokens + control head, same group 5-fold CV on the same 338 zones and folds as section 44) but the crop shrinks from the 3x3 cell to its outer-corner 60% x 60% (about 1.67x magnification). Only the crop extent changes. Paired comparison against the stored section-44 out-of-fold scores. Development evaluation. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


others = _load('others', 'tools/experiments/edge-back-triage-others-20261101/worker.py')
cv, bag, sw = others.cv, others.bag, others.sw
FRAC, DRAWS, SEED = 0.6, 2000, 20261101


def zoom(row):
    left, top, right, bottom = row['box']
    w, h = (right-left)*FRAC, (bottom-top)*FRAC
    x0 = left if row['area'].endswith('left') else right-w
    y0 = top if row['area'].startswith('upper') else bottom-h
    return dict(row, box=[x0, y0, x0+w, y0+h])


def paired_bootstrap(rows, new, old):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) < 2:
            continue
        diffs.append(bag.auc(sub, [new[i] for i in pick]) - bag.auc(sub, [old[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'edge-back-corner-zoom-cv-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    base = json.loads((ROOT/plan['baseline_observations']).read_text())
    if rows != ref['rows'] or rows != base['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    zrows = [zoom(r) for r in rows]
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, zrows, device)
    scores = others.oof_scores(x, m, zrows, cv.fold_of(rows))
    old = base['scores']
    auc_new, auc_old = bag.auc(rows, scores), bag.auc(rows, old)
    boot = paired_bootstrap(rows, scores, old)
    crit = dict(auc=auc_new >= plan['criterion_min_auc'], diff=auc_new - auc_old >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_zoom=auc_new, auc_baseline=auc_old, diff=auc_new-auc_old, diff_bootstrap=boot, rows=len(rows),
                   positive=sum(r['target'] for r in rows), groups=len({r['group'] for r in rows}), device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
