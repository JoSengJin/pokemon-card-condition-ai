"""Feature-dimension reduction for the control head: in-fold PCA of ViT-S/14 patch tokens to 128 (primary) or 64 dims before the same linear head. Same folds, rows, 448 input. Common-runner only."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import functools
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


def pca_basis(x, m, idx, dims):
    """Mean and top principal directions of the valid training tokens (fixed 150k-token subsample, seeded)."""
    tokens = x[idx][m[idx]]
    pick = torch.randperm(len(tokens), generator=torch.Generator().manual_seed(cv.SEED))[:150000]
    tokens = tokens[pick].double()
    mean = tokens.mean(0)
    _, _, v = torch.linalg.svd(tokens - mean, full_matrices=False)
    return mean.float(), v[:dims].T.float()


def project(x, mean, basis):
    return (x - mean) @ basis


def control_oof_pca(x, m, rows, fold, dims):
    scores = [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        mean, basis = pca_basis(x, m, t, dims)
        coef, bias, _ = sw.fit(project(x[t], mean, basis), m[t], [rows[i] for i in tr])
        for i, s in zip(ho, sw.score(project(x[h], mean, basis), m[h], coef, bias)):
            scores[i] = s
    return scores


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
    if not plan['hypothesis_id'].startswith('edge-back-pca-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    old = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows']:
        raise ValueError('Frozen holdout rows differ')
    base = json.loads((ROOT/plan['baseline_cv_scores']).read_text())
    base_ho = json.loads((ROOT/plan['baseline_holdout_scores']).read_text())
    if base['rows'] != old or base_ho['holdout_rows'] != test:
        raise ValueError('Frozen rows differ from the stored baselines')
    sw.check_separation(old, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xo, mo = sw.features(body, old, device)
    xt, mt = sw.features(body, test, device)
    fold = cv.fold_of(old)
    if fold != base['fold']:
        raise ValueError('Fold assignment differs from the baseline')
    everything = torch.arange(len(old))
    arms = {}
    for dims in plan['dims']:
        oof = control_oof_pca(xo, mo, old, fold, dims)
        mean, basis = pca_basis(xo, mo, everything, dims)
        coef, bias, _ = sw.fit(project(xo, mean, basis), mo, old)
        arms[str(dims)] = (oof, sw.score(project(xt, mean, basis), mt, coef, bias))
    primary = str(plan['primary_dims'])
    boot = {k: cv.bootstrap(old, base['control'], v[0]) for k, v in arms.items()}
    boot_ho = {k: cv.bootstrap(test, base_ho['holdout_base'], v[1]) for k, v in arms.items()}
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=arms[primary][1]), allow_nan=False))
    (out/'scores.json').write_text(json.dumps(dict(old_rows=old, oof={k: v[0] for k, v in arms.items()}, holdout_rows=test, holdout={k: v[1] for k, v in arms.items()}), allow_nan=False))
    at = lambda rs, sc: dict(auc=bag.auc(rs, sc), same_photo=bag.auc(rs, sc, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rs, sc)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rs, sc)))
    summary = dict(criterion_met=boot[primary]['delta']['lo'] > plan['criterion_min_delta_ci_lower'], primary_dims=plan['primary_dims'], cv_bootstrap=boot, cv_base=at(old, base['control']),
                   cv_arms={k: at(old, v[0]) for k, v in arms.items()}, holdout_bootstrap=boot_ho, holdout_base=at(test, base_ho['holdout_base']), holdout_arms={k: at(test, v[1]) for k, v in arms.items()},
                   groups=len(fold), rows=len(old), holdout_groups=len({r['group'] for r in test}), holdout_rows=len(test), max_iter=MAX_ITER, device=device,
                   typed_point_response='not_evaluated', training_calls=(cv.FOLDS + 1)*len(arms), external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
