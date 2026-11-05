"""C5 new-candidate dev: back-face observation-limit score, pooled dev (147 faces) + consumed holdout (120 faces), photo-group 5-fold CV. Single arm: v1.8 recipe (patch-mean + standardized L2 logistic) OOF scores on the pooled rows, AUC reported separately for the eBay-sourced rows and the development-sourced rows. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ms = _load('obsms', 'tools/experiments/obslimit-meanstd-20261101/worker.py')
bag, sw, cv = ms.bag, ms.sw, ms.cv
DRAWS, SEED = 2000, 20261103


def quality(row):
    """8 statistics of the confirmed card crop: Laplacian variance (log), highlight fraction, dark fraction, mean, std, edge density, box area, box aspect."""
    with Image.open(row['image']) as src:
        gray = np.asarray(ImageOps.exif_transpose(src).convert('L'), dtype=float)
    h, w = gray.shape
    x0, y0, x1, y1 = row['box']
    crop = gray[round(y0*h):round(y1*h), round(x0*w):round(x1*w)]
    lap = crop[1:-1, 1:-1]*4-crop[:-2, 1:-1]-crop[2:, 1:-1]-crop[1:-1, :-2]-crop[1:-1, 2:]
    grad = np.hypot(*np.gradient(crop))
    return [float(np.log1p(lap.var())), float((crop > 245).mean()), float((crop < 40).mean()), float(crop.mean()/255), float(crop.std()/255),
            float((grad > 20).mean()), (x1-x0)*(y1-y0), (x1-x0)*w/((y1-y0)*h)]


def oof(feats, rows, fold):
    scores = [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        te = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        for i, s in zip(te, ms.fit_predict(feats[tr], torch.tensor([rows[i]['target'] for i in tr]), feats[te])):
            scores[i] = s
    return scores


def paired(rows, control, treat):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng, diffs = random.Random(SEED), []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) > 1:
            diffs.append(bag.auc(sub, [treat[i] for i in pick])-bag.auc(sub, [control[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'obslimit-pooled-source-20261103':
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
    mean = (x*m[..., None]).sum(1)/m.sum(1, keepdim=True)
    fold = cv.fold_of(rows)
    scores = oof(mean, rows, fold)
    part = {name: [i for i, r in enumerate(rows) if (r['id'].startswith('ebay-pair-')) == (name == 'ebay')] for name in ('dev', 'ebay')}
    result = {}
    for name, sel in part.items():
        sub, sc = [rows[i] for i in sel], [scores[i] for i in sel]
        result[name] = dict(rows=len(sub), positive=sum(r['target'] for r in sub), auc=bag.auc(sub, sc), bootstrap=ms.auc_ci(sub, sc))
    criterion = dict(ebay_auc=result['ebay']['auc'] >= plan['criterion_min_auc'], ebay_lower=result['ebay']['bootstrap']['lo'] >= plan['criterion_min_auc_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, sources=result, pooled_auc=bag.auc(rows, scores), rows=len(rows), device=device,
                   typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
