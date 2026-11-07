"""Frozen-label views and exact weighted group-bootstrap metrics, no model calls."""
import numpy as np


def label_rows(rows, judgments):
    if not set(judgments).issubset({r['id'] for r in rows}):
        raise ValueError('Unknown judgment identity')
    if any(v not in ('정상', '결함', '불가') for v in judgments.values()):
        raise ValueError('Unresolved judgment must not become a training label')
    keep = [i for i, r in enumerate(rows) if judgments.get(r['id']) != '불가']
    original = [dict(rows[i]) for i in keep]
    revised = [dict(r, target=int(judgments[r['id']] == '결함')) if r['id'] in judgments else dict(r) for r in original]
    return keep, original, revised


def auc(labels, scores, weights=None):
    labels, scores = np.asarray(labels), np.asarray(scores)
    weights = np.ones(len(labels)) if weights is None else np.asarray(weights)
    _, inv = np.unique(scores, return_inverse=True)
    pos = np.bincount(inv, weights=weights * labels)
    neg = np.bincount(inv, weights=weights * (1-labels))
    if not pos.sum() or not neg.sum():
        raise ValueError('AUC requires both classes')
    return float((pos * (np.cumsum(neg)-neg/2)).sum() / (pos.sum()*neg.sum()))


def metrics(rows, scores):
    labels = np.array([r['target'] for r in rows])
    predictions = np.asarray(scores) >= .5
    pos, neg = int(labels.sum()), int(len(labels)-labels.sum())
    fn, fp = int(((labels==1) & ~predictions).sum()), int(((labels==0) & predictions).sum())
    return dict(rows=len(rows), positive=pos, negative=neg, auc=auc(labels,scores), fn=fn, fp=fp, fn_rate=fn/pos, fp_rate=fp/neg, threshold=.5)


def paired_bootstrap(rows, candidate, control, draws, seed):
    groups = sorted({r['group'] for r in rows})
    index = {g:i for i,g in enumerate(groups)}
    row_group = np.array([index[r['group']] for r in rows])
    labels = np.array([r['target'] for r in rows])
    rng = np.random.RandomState(seed)
    diffs = []
    for _ in range(draws):
        weights = np.bincount(rng.randint(len(groups),size=len(groups)),minlength=len(groups))[row_group]
        if not (weights*labels).sum() or not (weights*(1-labels)).sum():
            continue
        diffs.append(auc(labels,candidate,weights)-auc(labels,control,weights))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs), seed=seed, method='paired photo-group bootstrap; exact multiplicity-weighted AUC')
