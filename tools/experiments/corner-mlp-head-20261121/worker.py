"""Back-corner development CV: candidate E's recipe (same-photo pair ranking, DINOv2 ViT-S/14, 448 input, 946 zones, group folds) with the token scorer changed linear -> one-hidden-layer MLP (width 64, tanh). Only that variable changes. Control = candidate E's stored out-of-fold scores. Criteria: pooled AUC gain with a paired group bootstrap, same-photo AUC not lower, and card-level miss at matched false alarms not higher. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('head', ROOT/'tools/experiments/corner-mlp-head-20261121/head.py')
head = importlib.util.module_from_spec(spec)
spec.loader.exec_module(head)
corner = head.corner
bag, cv, sw, pool = corner.bag, corner.cv, corner.sw, corner.pool
SEED, V114_HIGH = 20261121, .60


def oof_mlp(x, m, rows):
    """Out-of-fold scores with the same group folds as candidate E; the MLP start is seeded per fold."""
    fold, scores = cv.fold_of(rows), [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        fitted = head.fit_head(x[t], m[t], [rows[i] for i in tr], 'mlp', SEED + f, head.MAX_ITER)
        for i, s in zip(ho, head.score_head(x[h], m[h], fitted, 'mlp')):
            scores[i] = s
    return scores


def card_miss(rows, scores, budget, fixed=None):
    """Smallest single threshold with at most `budget` normal-card false alarms (a normal card alarms when any zone >= t), or `fixed` when given; returns the missed positive cards there (a defect card is missed when all its defect zones < t)."""
    best, worst = defaultdict(lambda: -1.), defaultdict(float)
    for r, s in zip(rows, scores):
        if r['target']:
            best[r['group']] = max(best[r['group']], s)
        else:
            worst[r['group']] = max(worst[r['group']], s)
    normals = sorted(v for g, v in worst.items() if g not in best)
    t = fixed if fixed is not None else 0. if budget >= len(normals) else normals[-budget - 1] + 1e-12
    return dict(threshold=t, miss=sum(v < t for v in best.values()), positives=len(best), false_alarm=sum(v >= t for v in normals), normals=len(normals))


def verify(plan, ref, rows):
    """Refuse to run when the plan, mirrored sources, frozen inputs or frozen rows differ."""
    if plan['hypothesis_id'] != 'corner-mlp-head-20261121':
        raise ValueError('Wrong hypothesis')
    for name in ('worker.py', 'head.py'):
        if (Path(__file__).parent/name).read_bytes() != (ROOT/plan['tracked_directory']/name).read_bytes():
            raise ValueError('Mirror differs from tracked source: ' + name)
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    rows = json.loads((ROOT/plan['rows']).read_text())
    e_obs = json.loads((ROOT/plan['e_observations']).read_text())
    verify(plan, ref, rows)
    if rows != e_obs['rows']:
        raise ValueError('Control rows differ')
    torch.set_num_threads(8)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    x, m = sw.features(body.to(device), rows, device)
    scores, old = oof_mlp(x, m, rows), e_obs['scores']
    ctrl_budget = card_miss(rows, old, 10**6, V114_HIGH)['false_alarm']
    auc_new, auc_old = bag.auc(rows, scores), bag.auc(rows, old)
    same_new, same_old = bag.auc(rows, scores, True), bag.auc(rows, old, True)
    boot, boot_same = pool.paired_bootstrap(rows, scores, old), corner.paired_same_photo(rows, scores, old)
    matched = {b: dict(new=card_miss(rows, scores, b), control=card_miss(rows, old, b)) for b in sorted({5, ctrl_budget, 15})}
    crit = dict(auc_gain=auc_new - auc_old >= plan['min_auc_gain'] and boot['lo'] > plan['min_auc_gain_lower'], same_photo=same_new >= same_old,
                matched_miss=matched[ctrl_budget]['new']['miss'] <= matched[ctrl_budget]['control']['miss'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, e_linear_scores=old), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_mlp=auc_new, auc_linear=auc_old, auc_bootstrap=boot, same_photo_auc_mlp=same_new, same_photo_auc_linear=same_old,
                   same_photo_bootstrap=boot_same, control_false_alarm_budget=ctrl_budget, matched=matched, rows=len(rows), groups=len({r['group'] for r in rows}),
                   device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)


if __name__ == '__main__':
    run()
