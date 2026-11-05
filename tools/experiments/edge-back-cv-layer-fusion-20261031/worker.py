"""Pooled group 5-fold CV: control head on last-layer features vs mean of control heads on last-layer and 8th-block features. Same folds, seeds, rows as the grouped-CV baseline. Common-runner only."""
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


cv = _load('gcv', 'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
l8 = _load('l8w', 'tools/experiments/edge-back-layer8-pair-20261031/worker.py')
sw, bag = cv.sw, cv.bag


def control_oof(x, m, rows, fold):
    """Out-of-fold control-head scores (same fit/score calls as the baseline control arm)."""
    scores = [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        coef, bias, _ = sw.fit(x[t], m[t], [rows[i] for i in tr])
        for i, s in zip(ho, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
    return scores


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-cv-layer-fusion-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    val = [r for r in rows if r['split'] == 'val']
    if [sum(r['split'] == 'train' for r in rows), len(val)] != plan['expected_denominators']['train_val'] or [dict(r) for r in val] != ref['rows']:
        raise ValueError('Frozen denominator or reference rows changed')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    fold = cv.fold_of(rows)
    last = control_oof(*sw.features(body, rows, device), rows, fold)
    mid = control_oof(*l8.layer_features(body, rows, device), rows, fold)
    fused = [(a + b)/2 for a, b in zip(last, mid)]
    boot = cv.bootstrap(rows, last, fused)  # 'control' = last-layer control, 'pair' key = fused arm
    delta_ok = boot['delta']['lo'] > plan['criterion_min_delta_ci_lower']
    on_val = [i for i, r in enumerate(rows) if r['split'] == 'val']
    (out/'observations.json').write_text(json.dumps(dict(rows=[rows[i] for i in on_val], scores=[fused[i] for i in on_val]), allow_nan=False))
    (out/'oof_scores.json').write_text(json.dumps(dict(rows=rows, last=last, mid=mid, fused=fused, fold=fold), allow_nan=False))
    summary = dict(criterion_met=delta_ok, last_control=boot['control'], fused=boot['pair'], delta=boot['delta'],
                   oof=dict(last_auc=bag.auc(rows, last), mid_auc=bag.auc(rows, mid), fused_auc=bag.auc(rows, fused), last_same_photo=bag.auc(rows, last, True), fused_same_photo=bag.auc(rows, fused, True),
                            last_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rows, last)), last_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rows, last)),
                            fused_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rows, fused)), fused_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rows, fused))),
                   groups=len(fold), rows=len(rows), positive=sum(r['target'] for r in rows), normal=sum(1 - r['target'] for r in rows),
                   device=device, typed_point_response='not_evaluated', training_calls=2*cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
