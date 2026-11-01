"""Rule-based left/right centering from image geometry (no training): within the human-confirmed card box, find the outer card edge and the inner frame edge as the strongest horizontal-gradient peaks in fixed windows, then score = |L-R|/(L+R) of the two border widths. Compared with the human face-level centering label by AUC. Frozen windows, no tuning. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('feas', ROOT/'tools/experiments/centering-feasibility-20261101/worker.py')
feas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feas)
bag = feas.bag
WIDTH, BAND = 600, (0.18, 0.45)
FRONT_BAND, BACK_BAND = (0.18, 0.45), (0.25, 0.75)


def peak(values, lo, hi):
    lo, hi = max(0, int(lo)), min(len(values), int(hi))
    return None if hi <= lo else lo + int(np.argmax(values[lo:hi]))


def asymmetry(path, box, side):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('L')
    w, h = im.size
    crop = im.crop((int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h)))
    crop = crop.resize((WIDTH, max(8, round(crop.size[1]*WIDTH/crop.size[0]))))
    a = np.asarray(crop).astype(float)
    top, bottom = (FRONT_BAND if side == 'front' else BACK_BAND)
    band = a[int(a.shape[0]*top):int(a.shape[0]*bottom)]
    g = np.convolve(np.abs(np.diff(band.mean(0))), np.ones(3)/3, mode='same')
    n = len(g)
    ol = peak(g, 0, .12*n)
    il = peak(g, ol+.03*n, .35*n) if ol is not None else None
    orr = peak(g, .88*n, n)
    ir = peak(g, .65*n, orr-.03*n) if orr is not None else None
    if None in (ol, il, orr, ir) or il <= ol or orr <= ir:
        return None
    left, right = il-ol, orr-ir
    return abs(left-right)/(left+right)


def auc_ci(rows, scores, draws=2000, seed=20261101):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng, vals = random.Random(seed), []
    for _ in range(draws):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) > 1:
            vals.append(bag.auc(sub, [scores[i] for i in pick]))
    vals.sort()
    return dict(lo=vals[int(.025*(len(vals)-1))], hi=vals[int(.975*(len(vals)-1))], draws=len(vals))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'centering-geometry-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    raw = [asymmetry(r['image'], r['box'], r['side']) for r in rows]
    scores = [0. if s is None else s for s in raw]
    result = {}
    for side in ('front', 'back'):
        sel = [i for i, r in enumerate(rows) if r['side'] == side and raw[i] is not None]
        sub = [rows[i] for i in sel]
        sc = [scores[i] for i in sel]
        result[side] = dict(rows=len(rows) and sum(r['side'] == side for r in rows), detected=len(sel), positive=sum(r['target'] for r in sub), auc=bag.auc(sub, sc), bootstrap=auc_ci(sub, sc))
    crit = {s: result[s]['auc'] >= plan['criterion_min_auc'] and result[s]['bootstrap']['lo'] >= plan['criterion_min_auc_lower'] for s in result}
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, sides=result, undetected=sum(s is None for s in raw), typed_point_response='not_evaluated', training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
