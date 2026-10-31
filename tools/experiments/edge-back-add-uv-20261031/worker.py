"""Adds the 15 prefilled-page training photos (intakes u, v) to the 788-row control head. Out-of-fold AUC on the original rows with the same folds vs the stored baseline, plus the 36-photo holdout. Common-runner only."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import torch
import torch.optim
from PIL import Image, ImageOps
from torchvision.transforms.functional import normalize, to_tensor

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('gcv', ROOT/'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
bag, sw = cv.bag, cv.sw
SIZE, GRID, PATCH, MAX_ITER = 560, 40, 14, 300  # fixed before any score was seen
_lbfgs = torch.optim.LBFGS
torch.optim.LBFGS = lambda params, **kw: _lbfgs(params, **{**kw, 'max_iter': MAX_ITER})


def view(image, box):
    """Same crop and gray padding as side_experiment.prepared_image, at SIZE."""
    w, h = image.size
    region = (math.floor(box[0]*w), math.floor(box[1]*h), math.ceil(box[2]*w), math.ceil(box[3]*h))
    return ImageOps.pad(image.crop(region), (SIZE, SIZE), method=Image.Resampling.BILINEAR, color=(128, 128, 128)), region


def pixel_mask(region):
    """Resized-content pixels only (no padding), like physical_pixel_mask with halo 0."""
    cw, ch = region[2] - region[0], region[3] - region[1]
    rw, rh = ImageOps.contain(Image.new('L', (cw, ch)), (SIZE, SIZE)).size
    left, top = round((SIZE - rw)/2), round((SIZE - rh)/2)
    mask = torch.zeros((SIZE, SIZE), dtype=torch.bool)
    mask[top:top + rh, left:left + rw] = True
    return mask


def features(body, rows, device):
    by = {}
    for r in rows:
        by.setdefault(r['image'], []).append(r)
    done = {}
    with torch.inference_mode():
        for path, items in by.items():
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
            for r in items:
                resized, region = view(image, r['box'])
                tensor = normalize(to_tensor(resized), [.485, .456, .406], [.229, .224, .225])
                z = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
                if z.shape != (GRID*GRID, 384) or not torch.isfinite(z).all():
                    raise ValueError('Unexpected feature tensor')
                done[r['id']] = (z, pixel_mask(region).reshape(GRID, PATCH, GRID, PATCH).any(3).any(1).flatten())
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


def control_oof(x, m, rows, fold):
    scores = [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        coef, bias, _ = sw.fit(x[t], m[t], [rows[i] for i in tr])
        for i, s in zip(ho, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
    return scores


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-add-uv-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    old = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    new = json.loads((ROOT/plan['new_train_rows']).read_text())
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows']:
        raise ValueError('Frozen holdout rows differ')
    base = json.loads((ROOT/plan['baseline_cv_scores']).read_text())
    if base['rows'] != old:
        raise ValueError('Original rows differ from the stored baseline')
    sw.check_separation(old + new, test)
    if {r['group'] for r in old} & {r['group'] for r in new}:
        raise ValueError('New photos overlap the original rows')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xo, mo = sw.features(body, old, device)
    xn, mn = sw.features(body, new, device)
    xt, mt = sw.features(body, test, device)
    fold = cv.fold_of(old)
    if fold != base['fold']:
        raise ValueError('Fold assignment differs from the baseline')
    aug = [0.]*len(old)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(old) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(old) if fold[r['group']] == f]
        t, h = torch.tensor(tr), torch.tensor(ho)
        rows_tr = [old[i] for i in tr] + new
        sw.check_separation(rows_tr, [old[i] for i in ho])
        coef, bias, _ = sw.fit(torch.cat([xo[t], xn]), torch.cat([mo[t], mn]), rows_tr)
        for i, s in zip(ho, sw.score(xo[h], mo[h], coef, bias)):
            aug[i] = s
    boot = cv.bootstrap(old, base['control'], aug)  # 'control' = baseline, 'pair' key = +15 photos
    c0, b0, _ = sw.fit(xo, mo, old)
    c1, b1, _ = sw.fit(torch.cat([xo, xn]), torch.cat([mo, mn]), old + new)
    ho0, ho1 = sw.score(xt, mt, c0, b0), sw.score(xt, mt, c1, b1)
    boot_ho = cv.bootstrap(test, ho0, ho1)
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=ho1), allow_nan=False))
    (out/'scores.json').write_text(json.dumps(dict(old_rows=old, oof_aug=aug, holdout_rows=test, holdout_base=ho0, holdout_aug=ho1), allow_nan=False))
    at = lambda rs, sc: dict(auc=bag.auc(rs, sc), same_photo=bag.auc(rs, sc, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rs, sc)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rs, sc)))
    summary = dict(criterion_met=boot['delta']['mean'] <= plan['criterion_max_delta_mean'], cv_bootstrap=boot, cv_base=at(old, base['control']), cv_aug=at(old, aug),
                   holdout_bootstrap=boot_ho, holdout_base=at(test, ho0), holdout_aug=at(test, ho1), old_groups=len(fold), new_groups=len({r['group'] for r in new}), new_rows=len(new),
                   holdout_groups=len({r['group'] for r in test}), holdout_rows=len(test), device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS + 2, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
