"""Does a control head trained on the 788 original rows agree with the human labels of the 15 newly labeled photos often enough to prefill the label pages? Thresholds 0.6/0.4 fixed in advance. Common-runner only."""
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
    if not plan['hypothesis_id'].startswith('edge-back-prefill-agreement-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    old = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    new = json.loads((ROOT/plan['new_train_rows']).read_text())
    if new != ref['rows']:
        raise ValueError('Frozen new rows differ')
    sw.check_separation(old, new)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xo, mo = sw.features(body, old, device)
    xn, mn = sw.features(body, new, device)
    coef, bias, _ = sw.fit(xo, mo, old)
    scores = sw.score(xn, mn, coef, bias)
    hi, lo = plan['threshold_defect'], plan['threshold_normal']
    call = ['defect' if s >= hi else 'normal' if s <= lo else 'unsure' for s in scores]
    conf = [(c, r['target']) for c, r in zip(call, new) if c != 'unsure']
    correct = sum((c == 'defect') == bool(t) for c, t in conf)
    # taps on the label page cycle 미확인 -> 정상 -> 결함 -> 미확인 (normal 1 tap, defect 2 taps)
    base_taps = sum(2 if r['target'] else 1 for r in new)
    pre_taps = 0
    for c, r in zip(call, new):
        want = 2 if r['target'] else 1
        have = {'unsure': 0, 'normal': 1, 'defect': 2}[c]
        pre_taps += (want - have) % 3
    (out/'observations.json').write_text(json.dumps(dict(rows=new, scores=scores), allow_nan=False))
    summary = dict(criterion_met=len(conf)/len(new) >= plan['criterion_min_coverage'] and correct/len(conf) >= plan['criterion_min_confident_accuracy'],
                   rows=len(new), positive=sum(r['target'] for r in new), confident=len(conf), coverage=len(conf)/len(new), confident_correct=correct, confident_accuracy=correct/len(conf) if conf else None,
                   defect_calls=call.count('defect'), normal_calls=call.count('normal'), unsure=call.count('unsure'),
                   baseline_taps=base_taps, prefilled_taps=pre_taps, taps_saved_fraction=1 - pre_taps/base_taps, auc=bag.auc(new, scores),
                   threshold_defect=hi, threshold_normal=lo, device=device, typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
