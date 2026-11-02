"""C4 v1.9 dev: automatic front top/bottom border measurer. Outer edge = confirmed box edge; inner frame = strongest vertical gradient inside a fixed search window below the top / above the bottom edge, on the column-averaged central band. Score = |top-bottom|/(top+bottom). Compared with the human-marked values (36 dev fronts). No learning. Common-runner only."""
import hashlib
import json
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
BAND, WINDOW, SIGMA, DRAWS, SEED = (.25, .75), (.012, .09), 2.0, 2000, 20261103  # fixed before any score was seen


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


def widths(row):
    g = np.abs(profile(row))
    n = len(g)
    lo, hi = round(WINDOW[0]*n), round(WINDOW[1]*n)
    top = lo + int(np.argmax(g[lo:hi]))
    bottom = lo + int(np.argmax(g[::-1][lo:hi]))
    return top/n, bottom/n


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
    if plan['hypothesis_id'] != 'centering-tb-measurer-20261103':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    found = [widths(r) for r in rows]
    scores = [abs(t-b)/(t+b) for t, b in found]
    human = [r['human_tb'] for r in rows]
    spearman = float(np.corrcoef(rank(scores), rank(human))[0, 1])
    error = float(np.mean([abs(s-h) for s, h in zip(scores, human)]))
    value, boot = auc(rows, scores), bootstrap(rows, scores)
    criterion = dict(spearman=spearman >= plan['criterion_min_spearman'], auc=value >= plan['criterion_min_auc'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, spearman_with_human_marks=spearman, mean_abs_error_vs_human=error, auc_vs_label=value, bootstrap=boot,
                   human_mark_auc=auc(rows, human), rows=len(rows), positive=sum(r['target'] for r in rows), measured=[dict(id=r['id'], top=t, bottom=b, human_top=r['human_top'], human_bottom=r['human_bottom']) for r, (t, b) in zip(rows, found)],
                   typed_point_response='not_evaluated', training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'measured'}, ensure_ascii=False, default=float), flush=True)
