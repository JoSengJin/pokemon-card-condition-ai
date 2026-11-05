"""Pooled train+val group 5-fold CV of the pair-term head vs the control head (same recipes, final-layer features, full cells). Measures the pair-term effect on 137 photo groups instead of the 54-group validation. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('vsw', ROOT/'tools/experiments/edge-back-pair-vs-control-m-20261031/worker.py')
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)
pair, bag, sw = vs.pair, vs.bag, vs.sw
FOLDS, DRAWS, SEED = 5, 2000, 20261031  # fixed before any score was seen


def roc(pos, neg):
    return sum((a > b) + .5*(a == b) for a in pos for b in neg)/(len(pos)*len(neg))


def fold_of(rows):
    """Deterministic group -> fold map (shuffled with SEED, round robin)."""
    groups = sorted({r['group'] for r in rows})
    random.Random(SEED).shuffle(groups)
    return {g: i % FOLDS for i, g in enumerate(groups)}


def oof(x, m, rows, fold):
    """Out-of-fold scores for the control and pair arms."""
    control, paired, conv = [0.]*len(rows), [0.]*len(rows), []
    for f in range(FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        sub = [rows[i] for i in tr]
        c_coef, c_bias, _ = sw.fit(x[t], m[t], sub)
        p_coef, p_bias, p_conv = pair.fit_pair(x[t], m[t], sub)
        conv.append(p_conv)
        for i, s in zip(ho, sw.score(x[h], m[h], c_coef, c_bias)):
            control[i] = s
        for i, s in zip(ho, sw.score(x[h], m[h], p_coef, p_bias)):
            paired[i] = s
    return control, paired, conv


def bootstrap(rows, control, paired):
    """Resample photo groups; AUC of each arm and the paired pair-minus-control difference."""
    by = {}
    for i, r in enumerate(rows):
        by.setdefault(r['group'], []).append(i)
    keys, rng = sorted(by), random.Random(SEED)
    t = [r['target'] for r in rows]
    c, p, d = [], [], []
    for _ in range(DRAWS):
        idx = [i for g in (rng.choice(keys) for _ in keys) for i in by[g]]
        pos, neg = [i for i in idx if t[i]], [i for i in idx if not t[i]]
        ac, ap = roc([control[i] for i in pos], [control[i] for i in neg]), roc([paired[i] for i in pos], [paired[i] for i in neg])
        c.append(ac), p.append(ap), d.append(ap - ac)
    q = lambda v, a: sorted(v)[int(a*(len(v) - 1))]
    return {k: dict(mean=sum(v)/len(v), lo=q(v, .025), hi=q(v, .975)) for k, v in dict(control=c, pair=p, delta=d).items()}


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-grouped-cv-'):
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
    x, m = sw.features(body.to(device), rows, device)
    fold = fold_of(rows)
    control, paired, conv = oof(x, m, rows, fold)
    boot = bootstrap(rows, control, paired)
    half = (boot['pair']['hi'] - boot['pair']['lo'])/2
    on_val = [i for i, r in enumerate(rows) if r['split'] == 'val']
    (out/'observations.json').write_text(json.dumps(dict(rows=[rows[i] for i in on_val], scores=[paired[i] for i in on_val]), allow_nan=False))
    per_fold = [dict(fold=f, groups=sum(v == f for v in fold.values()), pair_auc=bag.auc([r for r in rows if fold[r['group']] == f], [paired[i] for i, r in enumerate(rows) if fold[r['group']] == f]),
                     control_auc=bag.auc([r for r in rows if fold[r['group']] == f], [control[i] for i, r in enumerate(rows) if fold[r['group']] == f])) for f in range(FOLDS)]
    delta_ok, width_ok = boot['delta']['lo'] > plan['criterion_min_delta_ci_lower'], half <= plan['criterion_max_half_width']
    summary = dict(criterion_met=delta_ok and width_ok, delta_ci_lower_positive=delta_ok, pair_half_width=half, bootstrap=boot,
                   oof=dict(pair_auc=bag.auc(rows, paired), pair_same_photo=bag.auc(rows, paired, True), control_auc=bag.auc(rows, control), control_same_photo=bag.auc(rows, control, True),
                            pair_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rows, paired)), pair_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rows, paired)),
                            control_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rows, control)), control_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rows, control))),
                   per_fold=per_fold, groups=len(fold), rows=len(rows), positive=sum(r['target'] for r in rows), normal=sum(1 - r['target'] for r in rows),
                   pair_convergence_all=all(c['converged'] for c in conv), device=device, typed_point_response='not_evaluated', training_calls=2*FOLDS, external_ai_calls=0)
    (out/'oof_scores.json').write_text(json.dumps(dict(rows=rows, control=control, pair=paired, fold=fold), allow_nan=False))
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
