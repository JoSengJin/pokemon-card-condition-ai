"""C4 v1.9 dev v5: v3 framework (outer anchor, window [outer+0.022, outer+0.049]) but the inner-frame pick is a learned candidate ranker (numpy logistic regression, L2) instead of argmax gradient. Candidates = local maxima of |gradient| in the window. Trained only on other photo groups (leave-one-group-out over the 36 dev fronts, targets = human widths measured from the detected outer edge); each row is scored by a model that never saw its group. No hold rule. Common-runner only."""
import hashlib
import json
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
BAND, WINDOW, SIGMA, DRAWS, SEED = (.25, .75), (.022, .049), 2.0, 2000, 20261103  # fixed before any score was seen
OUTER_ZONE, OUTER_MIN, TOL, L2, ITERS = .03, .004, .006, 1.0, 300  # fixed before any score was seen  # v3 outer-edge search zone / minimum offset, fixed before any score was seen


def profile(row):
    with Image.open(row['image']) as src:
        gray = np.asarray(ImageOps.exif_transpose(src).convert('L'), dtype=float)
    h, w = gray.shape
    x0, y0, x1, y1 = row['box']
    crop = gray[round(y0*h):round(y1*h), round(x0*w):round(x1*w)]
    cw = crop.shape[1]
    column = crop[:, round(BAND[0]*cw):round(BAND[1]*cw)].mean(1)
    kernel = np.exp(-.5*(np.arange(-8, 9)/SIGMA)**2)
    return np.gradient(np.convolve(column, kernel/kernel.sum(), mode='same'))


def outer_anchor(g):
    n = len(g)
    zone = g[:round(OUTER_ZONE*n)+1]
    p = int(np.argmax(zone))
    return p if p >= round(OUTER_MIN*n) else 0


def edge_padded_gradient(row):
    with Image.open(row['image']) as src:
        gray = np.asarray(ImageOps.exif_transpose(src).convert('L'), dtype=float)
    h, w = gray.shape
    x0, y0, x1, y1 = row['box']
    crop = gray[round(y0*h):round(y1*h), round(x0*w):round(x1*w)]
    cw = crop.shape[1]
    column = crop[:, round(BAND[0]*cw):round(BAND[1]*cw)].mean(1)
    kernel = np.exp(-.5*(np.arange(-8, 9)/SIGMA)**2)
    return np.abs(np.gradient(np.convolve(np.pad(column, 8, mode='edge'), kernel/kernel.sum(), mode='valid')))


def columns(row):
    with Image.open(row['image']) as src:
        rgb = np.asarray(ImageOps.exif_transpose(src).convert('RGB'), dtype=float)
    h, w, _ = rgb.shape
    x0, y0, x1, y1 = row['box']
    crop = rgb[round(y0*h):round(y1*h), round(x0*w):round(x1*w)]
    cw = crop.shape[1]
    return crop[:, round(BAND[0]*cw):round(BAND[1]*cw)].mean(1)  # (n, 3)


def edge_candidates(row):
    """Per side: anchor, window, list of (pos, feature vector), oriented from the outer edge inward."""
    col = columns(row)
    gray = col.mean(1)
    kernel = np.exp(-.5*(np.arange(-8, 9)/SIGMA)**2)
    kernel /= kernel.sum()
    n = len(gray)
    sides = []
    for flip in (False, True):
        c, g3 = (col[::-1], gray[::-1]) if flip else (col, gray)
        sm = np.convolve(g3, kernel, mode='same')
        sg = np.gradient(sm)
        ge = np.abs(np.gradient(np.convolve(np.pad(g3, 8, mode='edge'), kernel, mode='valid')))
        a = outer_anchor(ge)
        lo, hi = a+round(WINDOW[0]*n), min(a+round(WINDOW[1]*n), n-1)
        ab = np.abs(sg)
        med, top = float(np.median(ab[lo:hi]))+1e-6, float(ab[lo:hi].max())+1e-6
        cands = [p for p in range(lo+1, hi-1) if ab[p] >= ab[p-1] and ab[p] >= ab[p+1]] or [lo+int(np.argmax(ab[lo:hi]))]
        feats = []
        for p in cands:
            band = g3[a+2:max(p-2, a+3)]
            before, after = c[max(p-10, 0):max(p-3, 1)].mean(0), c[p+3:p+10].mean(0)
            sat = lambda v: float(v.max()-v.min())
            feats.append([ab[p]/med, ab[p]/top, 20*(p-a)/n, float(np.sign(sg[p])), float(band.std())/(float(g3.std())+1e-6),
                          abs(sat(after)-sat(before))/50, (float(after.mean())-float(before.mean()))/50])
        sides.append(dict(anchor=a, lo=lo, hi=hi, n=n, cands=cands, feats=np.array(feats)))
    return sides


def fit(X, y):
    mu, sd = X.mean(0), X.std(0)+1e-6
    Z = np.c_[np.ones(len(X)), (X-mu)/sd]
    w = np.zeros(Z.shape[1])
    for _ in range(ITERS):
        p = 1/(1+np.exp(-Z@w))
        w -= .5*(Z.T@(p-y)/len(y)+L2*np.r_[0, w[1:]]/len(y))
    return w, mu, sd


def score(model, feats):
    w, mu, sd = model
    return np.c_[np.ones(len(feats)), (feats-mu)/sd]@w


def training_set(all_sides, rows, exclude_group):
    X, y = [], []
    for sides, r in zip(all_sides, rows):
        if r['group'] == exclude_group:
            continue
        for side, human in zip(sides, (r['human_top'], r['human_bottom'])):
            target = side['anchor']+human*side['n']
            near = [abs(p-target) <= TOL*side['n'] for p in side['cands']]
            best = int(np.argmin([abs(p-target) for p in side['cands']]))
            if not near[best]:
                continue
            for k, f in enumerate(side['feats']):
                X.append(f)
                y.append(1.0 if k == best else 0.0)
    return np.array(X), np.array(y)


def measure_all(rows):
    all_sides = [edge_candidates(r) for r in rows]
    out = []
    for i, r in enumerate(rows):
        model = fit(*training_set(all_sides, rows, r['group']))
        one = []
        for side in all_sides[i]:
            k = int(np.argmax(score(model, side['feats'])))
            pos = side['cands'][k]
            one.append(dict(width=(pos-side['anchor'])/side['n'], anchor=side['anchor']/side['n'], pinned=pos in (side['lo'], side['hi']-1), ncand=len(side['cands'])))
        out.append(one)
    return out


def rank(values):
    order = np.argsort(values)
    ranks = np.empty(len(values))
    ranks[order] = np.arange(len(values))
    return ranks


def auc(rows, scores):
    pos = [s for r, s in zip(rows, scores) if r['target']]
    neg = [s for r, s in zip(rows, scores) if not r['target']]
    return sum((a > b) + .5*(a == b) for a in pos for b in neg)/(len(pos)*len(neg))


def bootstrap(rows, scores):
    rng, vals = random.Random(SEED), []
    for _ in range(DRAWS):
        pick = [rng.randrange(len(rows)) for _ in rows]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) > 1:
            vals.append(auc(sub, [scores[i] for i in pick]))
    vals.sort()
    return dict(lo=vals[int(.025*(len(vals)-1))], hi=vals[int(.975*(len(vals)-1))], draws=len(vals))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'centering-tb-measurer-v5-20261103':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    meas = measure_all(rows)
    found = [(m[0]['width'], m[1]['width']) for m in meas]
    pinned = sum(e['pinned'] for m in meas for e in m)
    valid = json.loads((ROOT/plan['valid_indices_file']).read_text())['slack_validity']['valid_heuristic_indices']
    scores = [abs(t-b)/(t+b) for t, b in found]
    human = [r['human_tb'] for r in rows]
    spearman = float(np.corrcoef(rank(scores), rank(human))[0, 1])
    error = float(np.mean([abs(s-h) for s, h in zip(scores, human)]))
    value, boot = auc(rows, scores), bootstrap(rows, scores)
    pinned_rate = pinned/(2*len(rows))
    hold_rate = 0.0  # no hold rule (single variable: learned pick)
    criterion = dict(spearman=spearman >= plan['criterion_min_spearman'], auc=value >= plan['criterion_min_auc'], hold=hold_rate <= plan['criterion_max_hold'], pinned=pinned_rate < plan['criterion_pinned_below'])
    sub = [rows[i] for i in valid]
    sub_scores = [scores[i] for i in valid]
    sub_human = [human[i] for i in valid]
    subset = dict(n=len(sub), positive=sum(r['target'] for r in sub), spearman=float(np.corrcoef(rank(sub_scores), rank(sub_human))[0, 1]), auc=auc(sub, sub_scores))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, pinned_edges=pinned, edges=2*len(rows), pinned_rate=pinned_rate, v2_pinned_rate=22/72, hold_rate=hold_rate, valid_subset_heuristic19=subset, spearman_with_human_marks=spearman, mean_abs_error_vs_human=error, auc_vs_label=value, bootstrap=boot,
                   human_mark_auc=auc(rows, human), rows=len(rows), positive=sum(r['target'] for r in rows), measured=[dict(id=r['id'], top=t, bottom=b, anchor_top=m[0]['anchor'], anchor_bottom=m[1]['anchor'], human_top=r['human_top'], human_bottom=r['human_bottom']) for r, (t, b), m in zip(rows, found, meas)],
                   typed_point_response='not_evaluated', training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'measured'}, ensure_ascii=False, default=float), flush=True)
