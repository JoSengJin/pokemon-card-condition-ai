"""Back-corner development CV: same-photo pairwise ranking term (defect corner > normal corner of the same photo) vs the control recipe on all labelled back-corner zones (pooled), group 5-fold out-of-fold with the same folds for both arms. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from collections import Counter
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pair = _load('pair', 'tools/experiments/edge-back-same-photo-pair-20261031/worker.py')
pool = _load('pool', 'tools/experiments/surface-newdef-pool-cv-r2-20261102/worker.py')
cv, bag, sw = pool.cv, pool.bag, pool.sw
DRAWS, SEED = 2000, 20261102


def guarded_masses(rows):
    """pair.masses with the source rebalancing applied only when both eBay and non-eBay groups exist (0/0 otherwise)."""
    y = torch.tensor([r['target'] for r in rows])
    count = Counter(r['group'] for r in rows)
    mass = torch.tensor([1/count[r['group']] for r in rows], dtype=torch.float64)
    ebay = torch.tensor([r['group'].startswith('ebay') for r in rows])
    if (~ebay).any() and ebay.any():
        mass[ebay] *= mass[~ebay].sum()/mass[ebay].sum()
    mass[y == 1] *= mass[y == 0].sum()/mass[y == 1].sum()
    return y, mass/mass.sum()


def control_fit(x, masks, rows):
    """Control recipe (guarded rebalancing) with a larger LBFGS iteration cap as a convergence stop rule."""
    lbfgs = torch.optim.LBFGS
    torch.optim.LBFGS = lambda params, **kw: lbfgs(params, **{**kw, 'max_iter': 1000})
    try:
        return pool.fit_pool(x, masks, rows)
    finally:
        torch.optim.LBFGS = lbfgs


def oof(x, m, rows, fit):
    fold, scores = cv.fold_of(rows), [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        coef, bias, _ = fit(x[t], m[t], [rows[i] for i in tr])
        for i, s in zip(ho, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
    return scores


def paired_same_photo(rows, new, old):
    """Paired group bootstrap of the same-photo AUC difference (resampled photos keep their identity per draw)."""
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng, diffs = random.Random(SEED), []
    for _ in range(DRAWS):
        sub, a, b, n = [], [], [], 0
        for g in [rng.choice(keys) for _ in keys]:
            n += 1
            for i in idx[g]:
                sub.append(dict(rows[i], image=f'{rows[i]["image"]}#{n}', group=f'{g}#{n}'))
                a.append(new[i]); b.append(old[i])
        if any(r['target'] for r in sub) and any(not r['target'] for r in sub) and len({r['image'] for r in sub if r['target']} & {r['image'] for r in sub if not r['target']}):
            diffs.append(bag.auc(sub, a, True) - bag.auc(sub, b, True))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs) - 1))], hi=diffs[int(.975*(len(diffs) - 1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'corner-same-photo-pair-cv-20261102':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    pair.masses = guarded_masses
    control, paired = oof(x, m, rows, control_fit), oof(x, m, rows, pair.fit_pair)
    boot = paired_same_photo(rows, paired, control)
    auc_all, same_c, same_p = (bag.auc(rows, paired), bag.auc(rows, control, True), bag.auc(rows, paired, True))
    crit = dict(same_photo=same_p - same_c >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=paired, control_scores=control), allow_nan=False))
    cnt = lambda s: dict(fn=sum(r['target'] == 1 and v < .5 for r, v in zip(rows, s)), fp=sum(r['target'] == 0 and v >= .5 for r, v in zip(rows, s)))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, same_photo_auc_pair=same_p, same_photo_auc_control=same_c, same_photo_diff=same_p - same_c, same_photo_bootstrap=boot,
                   auc_pair=auc_all, auc_control=bag.auc(rows, control), pair_counts=cnt(paired), control_counts=cnt(control), positive=sum(r['target'] for r in rows),
                   normal=sum(1 - r['target'] for r in rows), rows=len(rows), groups=len({r['group'] for r in rows}), lambda_pair=pair.LAMBDA, device=device,
                   typed_point_response='not_evaluated', training_calls=2*cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
