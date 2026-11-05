"""Feasibility of the inspection-priority use for other categories (corner back/front, surface back/front, edge front) with the same recipe: pooled group 5-fold CV of the control head (ViT-S/14 448 tokens). Band thresholds per category come from its own out-of-fold defect scores (10% / 30% of defects below). Descriptive development evaluation. Common-runner only."""
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
tr = _load('triage', 'tools/experiments/edge-back-triage-holdout-20261031/worker.py')
bag, sw = cv.bag, cv.sw


def oof_scores(x, m, rows, fold):
    scores = [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr_i = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr_i], [rows[i] for i in ho])
        t, h = torch.tensor(tr_i), torch.tensor(ho)
        coef, bias, _ = sw.fit(x[t], m[t], [rows[i] for i in tr_i])
        for i, s in zip(ho, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
    return scores


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-triage-others-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows_all = json.loads((ROOT/plan['rows']).read_text())
    if rows_all != ref['rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    result, all_scores = {}, [None]*len(rows_all)
    for cat in plan['categories']:
        idx = [i for i, r in enumerate(rows_all) if r['category'] == cat]
        rows = [rows_all[i] for i in idx]
        try:
            x, m = sw.features(body, rows, device)
            scores = oof_scores(x, m, rows, cv.fold_of(rows))
            del x, m
        except ValueError as exc:
            result[cat] = dict(status='failed', error=str(exc), rows=len(rows))
            for i in idx:
                all_scores[i] = 0.5
            continue
        for i, s in zip(idx, scores):
            all_scores[i] = s
        pos = sorted(s for r, s in zip(rows, scores) if r['target'])
        low, high = pos[int(.10*len(pos))], pos[int(.30*len(pos))]
        met = tr.metrics(rows, scores, low, high)
        boot = tr.bootstrap(rows, scores, low, high)
        feasible = bag.auc(rows, scores) >= plan['feasible_min_auc'] and met['gap'] is not None and met['gap'] >= plan['feasible_min_gap']
        result[cat] = dict(status='completed', rows=len(rows), positive=sum(r['target'] for r in rows), normal=sum(1 - r['target'] for r in rows), groups=len({r['group'] for r in rows}),
                           auc=bag.auc(rows, scores), same_photo=bag.auc(rows, scores, True) if any(a['image'] == b['image'] and a['target'] != b['target'] for a in rows[:60] for b in rows[:60]) or True else None,
                           low=low, high=high, metrics=met, bootstrap=boot, feasible=feasible)
    (out/'observations.json').write_text(json.dumps(dict(rows=rows_all, scores=all_scores), allow_nan=False))
    summary = dict(criterion_met=any(v.get('feasible') for v in result.values()), categories=result, feasible_min_auc=plan['feasible_min_auc'], feasible_min_gap=plan['feasible_min_gap'],
                   device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS*len(plan['categories']), external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
