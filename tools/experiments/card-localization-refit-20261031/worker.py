"""Card-localization refit candidate: autobox.propose plus 2 color-model refits from the first-pass mask, then 10% widen. Inference-free (numpy/PIL only)."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s2 = _load('locs2', 'tools/experiments/card-localization-stage2-20261031/worker.py')
wid, ab = s2.wid, s2.ab
REFITS = 2
MIN_PIXELS = 50
MARGIN = .02


def mask_of(a, refits):
    """Seed models as autobox does (ring=bg, center=fg); then refit both models from the current mask `refits` times."""
    h, w = a.shape[:2]
    ring = np.ones((h, w), bool)
    ring[int(h*.06):int(h*.94), int(w*.06):int(w*.94)] = False
    core = np.zeros((h, w), bool)
    core[int(h*.35):int(h*.65), int(w*.35):int(w*.65)] = True
    bg, fg = ab._model(a[ring]), ab._model(a[core])
    mask = ab._dist(a, *fg) < ab._dist(a, *bg)
    for _ in range(refits):
        if mask.sum() < MIN_PIXELS or (~mask).sum() < MIN_PIXELS:
            break
        bg, fg = ab._model(a[~mask]), ab._model(a[mask])
        mask = ab._dist(a, *fg) < ab._dist(a, *bg)
    return mask


def propose(path, refits=REFITS):
    """Same projection, thresholds, margin and confidence as autobox.propose; only the mask differs."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((400, 400))
        a = np.asarray(im).astype(float)
    h, w = a.shape[:2]
    mask = mask_of(a, refits)
    col, row = mask.mean(0), mask.mean(1)
    cx, ry = np.where(col > .35*col.max())[0], np.where(row > .35*row.max())[0]
    if not len(cx) or not len(ry) or col.max() <= 0:
        return [0.1, 0.1, 0.9, 0.9], 0.0
    l, r, t, b = cx.min()/w, (cx.max() + 1)/w, ry.min()/h, (ry.max() + 1)/h
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1) or r - l < .15 or b - t < .15:
        return [0.1, 0.1, 0.9, 0.9], 0.0
    fill = mask[int(t*h):int(b*h), int(l*w):int(r*w)].mean()
    conf = float(min(1, fill/.8)*(1 if .25 <= (r - l)*(b - t) <= .9 else .4))
    box = [max(0, l - MARGIN), max(0, t - MARGIN), min(1, r + MARGIN), min(1, b + MARGIN)]
    return [round(float(v), 4) for v in box], round(conf, 3)


def evaluate(rows):
    """Guard: refits=0 must reproduce autobox.propose exactly; then judge the widened refit box."""
    detail = []
    for r in rows:
        if propose(r['image'], 0) != tuple(ab.propose(r['image'])):
            raise ValueError('refits=0 differs from autobox: ' + r['id'])
        raw, conf = propose(r['image'])
        box = wid.widen(raw)
        detail.append(dict(id=r['id'], batch=r['batch'], fresh=r['fresh'], raw_box=raw, box=box, conf=conf, area_ratio=s2.base.area_ratio(box, r['box']),
                           contained=s2.base.contained(box, r['corners']), passes=wid.passes(box, r)))
    return detail


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('card-localization-refit-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = s2.faces()
    if json.loads(json.dumps(rows)) != ref['rows'] or len(rows) != plan['expected_denominators']['dev_faces']:
        raise ValueError('Dev face set or reference rows changed')
    detail = evaluate(rows)
    scores = [1.0 if d['passes'] else 0.0 for d in detail]
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores), allow_nan=False))
    met_before = [b == 1.0 for b in ref['before_scores']]
    unmet = sum(not d['passes'] for d in detail)
    newly = [d['id'] for d, m in zip(detail, met_before) if m and not d['passes']]
    summary = dict(faces=len(detail), unmet=unmet, unmet_rate=unmet/len(detail), wilson95=s2.base.wilson(unmet, len(detail)), before_unmet=met_before.count(False),
                   newly_unmet=newly, recovered=[d['id'] for d, m in zip(detail, met_before) if not m and d['passes']],
                   criterion_max_unmet=plan['acceptance']['max_fn'], criterion_max_newly=1, criterion_met=unmet <= plan['acceptance']['max_fn'] and len(newly) <= 1,
                   detail=detail, refits=REFITS, training_calls=0, external_ai_calls=0, model_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'detail'}, ensure_ascii=False, default=float), flush=True)
