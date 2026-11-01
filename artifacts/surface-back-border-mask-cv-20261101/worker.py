"""Back-surface border mask: same recipe (ViT-S/14 448 tokens + control head, same 411 zones and group folds as section 42) but patches within 20% of the cell width/height of the CARD perimeter (outer sides of perimeter cells; card edge, corners and background) are removed from both training and scoring. Only the patch mask changes. Paired comparison against stored section-42 out-of-fold scores. Development evaluation. Common-runner only."""
import hashlib
import importlib.util
import json
import math
import os
import random
from pathlib import Path

import torch
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


others = _load('others', 'tools/experiments/edge-back-triage-others-20261101/worker.py')
cv, bag, sw = others.cv, others.bag, others.sw
MARGIN, DRAWS, SEED = 0.20, 2000, 20261101
CELL = {'upper_left': (0, 0), 'upper_center': (1, 0), 'upper_right': (2, 0), 'middle_left': (0, 1), 'center': (1, 1), 'middle_right': (2, 1),
        'lower_left': (0, 2), 'lower_center': (1, 2), 'lower_right': (2, 2)}


def border_mask(row):
    x, y = CELL[row['area']]
    with Image.open(row['image']) as im:
        w, h = ImageOps.exif_transpose(im).size
    box = row['box']
    cw, ch = math.ceil(box[2]*w)-math.floor(box[0]*w), math.ceil(box[3]*h)-math.floor(box[1]*h)
    rw, rh = ImageOps.contain(Image.new('L', (cw, ch)), (448, 448)).size
    left, top = round((448-rw)/2), round((448-rh)/2)
    mask = torch.ones(32, 32, dtype=torch.bool)
    for i in range(32):
        for j in range(32):
            u, v = ((j+.5)*14-left)/rw, ((i+.5)*14-top)/rh
            if (x == 0 and u < MARGIN) or (x == 2 and u > 1-MARGIN) or (y == 0 and v < MARGIN) or (y == 2 and v > 1-MARGIN):
                mask[i, j] = False
    return mask.flatten()


def paired_bootstrap(rows, new, old):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) < 2:
            continue
        diffs.append(bag.auc(sub, [new[i] for i in pick]) - bag.auc(sub, [old[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-back-border-mask-cv-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    all_rows = json.loads((ROOT/plan['rows']).read_text())
    base = json.loads((ROOT/plan['baseline_observations']).read_text())
    if all_rows != base['rows']:
        raise ValueError('Baseline rows differ')
    idx = [i for i, r in enumerate(all_rows) if r['category'] == plan['category']]
    rows = [all_rows[i] for i in idx]
    old = [base['scores'][i] for i in idx]
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    m2 = m & torch.stack([border_mask(r) for r in rows])
    if (m2.sum(1) == 0).any():
        raise ValueError('A zone lost all patches')
    scores = others.oof_scores(x, m2, rows, cv.fold_of(rows))
    auc_new, auc_old = bag.auc(rows, scores), bag.auc(rows, old)
    boot = paired_bootstrap(rows, scores, old)
    per = {}
    for name, sel in (('perimeter', [i for i, r in enumerate(rows) if r['area'] != 'center' and CELL[r['area']] != (1, 1)]), ('center', [i for i, r in enumerate(rows) if r['area'] == 'center'])):
        sub = [rows[i] for i in sel]
        per[name] = dict(rows=len(sub), auc_new=bag.auc(sub, [scores[i] for i in sel]) if len({r['target'] for r in sub}) > 1 else None,
                         auc_old=bag.auc(sub, [old[i] for i in sel]) if len({r['target'] for r in sub}) > 1 else None)
    crit = dict(diff=auc_new-auc_old >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_mask=auc_new, auc_baseline=auc_old, diff=auc_new-auc_old, diff_bootstrap=boot, by_cell_group=per, rows=len(rows),
                   positive=sum(r['target'] for r in rows), groups=len({r['group'] for r in rows}), kept_patch_fraction=float(m2.sum()/m.sum()), device=device,
                   typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
