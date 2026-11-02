"""Candidate D: fine-tune the last 2 DINOv2 blocks on zone crops with a same-photo pair ranking loss, group 5-fold out-of-fold on the 1791 new-definition back-surface zones (same folds as the earlier pooled runs); control = frozen-recipe (linear head on frozen last-layer tokens) out-of-fold scores of the pooled run 20261102T104152-f953c270. Development CV, common-runner only."""
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


ft = _load('ft', 'tools/experiments/surface-ft-pair-cv-20261102/ft.py')
pool = _load('pool', 'tools/experiments/surface-newdef-pool-cv-r2-20261102/worker.py')
cv, bag, sw = pool.cv, pool.bag, pool.sw


def check_inputs(plan, ref):
    if plan['hypothesis_id'] != 'surface-ft-pair-cv-20261102':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    control = json.loads((ROOT/plan['control_scores']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows'] or len(control) != len(rows):
        raise ValueError('Frozen rows differ')
    return rows, control


def oof(body, X, M, rows, device):
    fold = cv.fold_of(rows)
    scores, history = [0.]*len(rows), []
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        model, losses = ft.train_fold(body, X, M, rows, tr, device)
        for i, s in zip(ho, ft.score(model, X, M, ho, device)):
            scores[i] = s
        history.append(dict(fold=f, train=len(tr), steps=len(losses), first=sum(losses[:10])/10, last=sum(losses[-10:])/10))
    return scores, history


def summarize(rows, scores, control, plan, history, device):
    boot = pool.paired_bootstrap(rows, scores, control)
    auc_d, auc_b = bag.auc(rows, scores), bag.auc(rows, control)
    crit = dict(diff=auc_d - auc_b >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    cnt = lambda s: dict(fn=sum(r['target'] == 1 and v < .5 for r, v in zip(rows, s)), fp=sum(r['target'] == 0 and v >= .5 for r, v in zip(rows, s)))
    return dict(criterion_met=all(crit.values()), criterion=crit, auc_candidate_d=auc_d, auc_frozen_control=auc_b, diff=auc_d - auc_b, diff_bootstrap=boot,
                same_photo_auc_d=bag.auc(rows, scores, True), same_photo_auc_control=bag.auc(rows, control, True), d_counts=cnt(scores), control_counts=cnt(control),
                positive=sum(r['target'] for r in rows), normal=sum(1 - r['target'] for r in rows), rows=len(rows), groups=len({r['group'] for r in rows}),
                fold_history=history, config=ft.CFG, device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    rows, control = check_inputs(plan, json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text()))
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    X, M = ft.cache_tokens(body, rows, device)
    scores, history = oof(body, X, M, rows, device)
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, control_scores=control), allow_nan=False))
    summary = summarize(rows, scores, control, plan, history, device)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
