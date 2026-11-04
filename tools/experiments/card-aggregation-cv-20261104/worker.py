"""Card-level aggregation rule on development out-of-fold zone scores (two-backbone ensemble scores of surface and back corner). Baseline = max zone score (equal to 'any zone above a threshold'); candidate = logistic regression on the top-3 sorted zone logits, card group 5-fold. Paired card bootstrap of the card-level AUC difference. No new image inference; common-runner only."""
import hashlib
import json
import math
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
SEED, DRAWS, FOLDS, TOP, L2, RECALL = 20261104, 2000, 5, 3, 1.0, 0.9


def logit(p):
    p = min(max(p, 1e-4), 1-1e-4)
    return math.log(p/(1-p))


def cards_of(rows, scores):
    by = {}
    for r, s in zip(rows, scores):
        by.setdefault(r['group'], []).append((r['target'], logit(s)))
    keys = sorted(by)
    feats = [sorted((s for _, s in by[g]), reverse=True)[:TOP] for g in keys]
    feats = [f + [f[-1]]*(TOP-len(f)) for f in feats]
    return keys, [int(any(t for t, _ in by[g])) for g in keys], feats


def auc(y, s):
    pos, neg = [a for a, t in zip(s, y) if t], [a for a, t in zip(s, y) if not t]
    return sum((p > q) + .5*(p == q) for p in pos for q in neg)/(len(pos)*len(neg))


def fit(x, y):
    x, y = torch.tensor(x, dtype=torch.float64), torch.tensor(y, dtype=torch.float64)
    w = torch.zeros(x.shape[1], dtype=torch.float64, requires_grad=True)
    b = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([w, b], max_iter=500, tolerance_grad=1e-9, tolerance_change=1e-12)

    def closure():
        opt.zero_grad()
        z = x@w + b
        loss = torch.nn.functional.binary_cross_entropy_with_logits(z, y) + L2*(w*w).sum()/(2*len(y))
        loss.backward()
        return loss
    opt.step(closure)
    return w.detach(), b.detach()


def oof(feats, y):
    order = sorted(range(len(y)), key=lambda i: i)
    rng = random.Random(SEED)
    idx = list(order)
    rng.shuffle(idx)
    fold = {i: k % FOLDS for k, i in enumerate(idx)}
    learned, base = [0.]*len(y), [f[0] for f in feats]
    for f in range(FOLDS):
        tr = [i for i in order if fold[i] != f]
        ho = [i for i in order if fold[i] == f]
        w, b = fit([feats[i] for i in tr], [y[i] for i in tr])
        for i in ho:
            learned[i] = float(torch.tensor(feats[i], dtype=torch.float64)@w + b)
    return learned, base, fold


def operating(y, s, fold):
    """Per held-out fold: threshold = score quantile on the training folds giving >= RECALL on training positives; report held-out recall and false-alarm rate."""
    tp = fp = pos = neg = 0
    for f in range(FOLDS):
        tr = [i for i in range(len(y)) if fold[i] != f]
        ho = [i for i in range(len(y)) if fold[i] == f]
        ps = sorted(s[i] for i in tr if y[i])
        thr = ps[int((1-RECALL)*len(ps))]
        for i in ho:
            if y[i]:
                pos += 1; tp += s[i] >= thr
            else:
                neg += 1; fp += s[i] >= thr
    return dict(recall=tp/pos, false_alarm=fp/neg, positives=pos, normals=neg)


def boot(y, a, b):
    rng, diffs = random.Random(SEED), []
    n = len(y)
    for _ in range(DRAWS):
        pick = [rng.randrange(n) for _ in range(n)]
        yy = [y[i] for i in pick]
        if 0 < sum(yy) < n:
            diffs.append(auc(yy, [a[i] for i in pick]) - auc(yy, [b[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'card-aggregation-cv-20261104':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows, scores, cells, result = [], [], {}, {}
    for name, path in plan['cells'].items():
        obs = json.loads((ROOT/path).read_text())
        cells[name] = (obs['rows'], obs['scores'])
        rows += obs['rows']; scores += obs['scores']
    if rows != ref['rows']:
        raise ValueError('Frozen rows differ')
    ok = []
    for name, (r, s) in cells.items():
        keys, y, feats = cards_of(r, s)
        learned, base, fold = oof(feats, y)
        d = boot(y, learned, base)
        a_l, a_b = auc(y, learned), auc(y, base)
        met = a_l-a_b >= plan['criterion_min_diff'] and d['lo'] > plan['criterion_min_diff_lower']
        ok.append(met)
        result[name] = dict(cards=len(y), defect_cards=sum(y), auc_learned=a_l, auc_max=a_b, diff=a_l-a_b, bootstrap=d, criterion_met=met,
                            operating_learned=operating(y, learned, fold), operating_max=operating(y, base, fold))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(ok), cells=result, typed_point_response='not_evaluated', training_calls=2*FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
