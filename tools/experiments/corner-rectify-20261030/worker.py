"""Corner-rectify comparison: same head, same 8 edge areas, only the cropping changes (auto box vs 4-corner perspective rectify).
Inference only; no training, no external model calls. Common-runner only."""
import json
import os
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'artifacts/inner-whitening-confounder-20261021'))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402
from torchvision.transforms.functional import normalize, to_tensor  # noqa: E402
from card_condition.ebay_dataset import decoded_hash  # noqa: E402
from card_condition.regions import GLARE_AREAS, region_box  # noqa: E402
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import prepared_image  # noqa: E402

EDGE_AREAS = tuple(a for a in GLARE_AREAS if a != 'center')
RUN = 'artifacts/experiments/20261030T113857-2deb9558'
INTAKE = 'artifacts/ebay-intake-20261030-f'
EXCLUDED = 'ebay-pair-562d461bcf3f22'  # user-confirmed: card cut off by the photo edge
DEFECT = [f'ebay-pair-{i}' for i in ('701e054702656a', '6023b3b2ff7e03', '1d280da40ebec0', '8d2e69973ad434',
                                     '9ad04666c74753', '18080c170dfe6c', '3a1557979e65a0', '6e9e2bf9f82f94')]
UNJUDGEABLE = [f'ebay-pair-{i}' for i in ('c29f4cd0872f3d', '91a731bb064215', '61ee246bc9ba1d')]
THRESHOLD = .5


def load_corners(text):
    """'id=x1:y1;x2:y2;x3:y3;x4:y4' (TL, TR, BR, BL, normalized); comment lines ignored."""
    corners = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith('#') or '=' not in line:
            continue
        key, value = line.strip().split('=', 1)
        points = [tuple(float(v) for v in p.split(':')) for p in value.split(';')]
        if len(points) != 4 or any(len(p) != 2 or not all(0 <= v <= 1 for v in p) for p in points):
            raise ValueError('Bad corner answer: ' + key)
        corners[key] = points
    return corners


def homography(src, dst):
    """3x3 H with H @ (x, y, 1) ~ (u, v, 1) for 4 point pairs (pixel coordinates), h33 = 1."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u*x, -u*y]); b.append(u)
        a.append([0, 0, 0, x, y, 1, -v*x, -v*y]); b.append(v)
    h = np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64))
    return np.append(h, 1.).reshape(3, 3)


def apply_h(h, point):
    x, y, w = h @ np.array([point[0], point[1], 1.])
    return x/w, y/w


def rectify(image, corners):
    """Warp so the 4 normalized corners (TL, TR, BR, BL) land on (0,0), (W,0), (W,H), (0,H); output size = input size."""
    w, h = image.size
    src = [(x*w, y*h) for x, y in corners]
    dst = [(0, 0), (w, 0), (w, h), (0, h)]
    inverse = homography(dst, src)  # PIL maps output pixel -> source pixel
    coeffs = (inverse/inverse[2, 2]).flatten()[:8].tolist()
    return image.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BILINEAR)


def load_image(path):
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert('RGB')


def face_score(body, device, image, path, card_box, coef, bias):
    """Max over the 8 edge areas of the head's masked patch-logit max; same ops as the 20261030T113857 run."""
    scores = {}
    with torch.inference_mode():
        for area in EDGE_AREAS:
            box = region_box(card_box, area)
            view = prepared_image(image, box, True, 448)
            tensor = normalize(to_tensor(view), [.485, .456, .406], [.229, .224, .225])
            z = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
            if z.shape != (1024, 384) or not torch.isfinite(z).all():
                raise ValueError('Unexpected feature tensor')
            mask = physical_pixel_mask(path, box, halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
            logits = z @ coef + bias
            scores[area] = float(logits.masked_fill(~mask, -torch.inf).amax().sigmoid())
    return scores


def load_body(plan, device):
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    return body.to(device)


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('corner-rectify-edge-'):
        raise ValueError('Wrong hypothesis')
    base = json.loads((ROOT/RUN/'plan.json').read_text())
    faces = {f['id']: f for f in json.loads((ROOT/INTAKE/'back-faces.json').read_text())}
    corners = load_corners((ROOT/INTAKE/'corner-answers.txt').read_text())
    ids = [i for i in corners if i != EXCLUDED]
    if sorted(ids) != sorted(DEFECT + UNJUDGEABLE) or [r['id'] for r in ref['rows']] != DEFECT:
        raise ValueError('Face set or reference order changed')
    for i in ids:  # photo bytes must match the frozen intake list
        if decoded_hash(Path(faces[i]['image']).read_bytes())[0] != faces[i]['sha']:
            raise ValueError('Photo content changed: ' + i)
    head = torch.load(ROOT/RUN/'head.pt', map_location='cpu', weights_only=True)
    coef, bias = head['coef'], head['bias']
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = load_body(base, device)
    axis, flat, regions = {}, {}, {}
    for i in ids:
        path = faces[i]['image']
        image = load_image(path)
        a = face_score(body, device, image, path, faces[i]['box'], coef, bias)
        r = face_score(body, device, rectify(image, corners[i]), path, [0, 0, 1, 1], coef, bias)
        axis[i], flat[i], regions[i] = max(a.values()), max(r.values()), dict(axis=a, rectified=r)
    # reference must be the same computation as the frozen axis-aligned scores
    if any(abs(axis[i] - s) > 1e-4 for i, s in zip(DEFECT, ref['before_scores'])):
        raise ValueError('Axis-aligned scores differ from the frozen reference; stopping')
    scores = [flat[i] for i in DEFECT]
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores), allow_nan=False))
    caught_axis = [i for i in DEFECT if axis[i] >= THRESHOLD]
    caught_rect = [i for i in DEFECT if flat[i] >= THRESHOLD]
    summary = dict(defect_denominator=len(DEFECT), axis_detected=len(caught_axis), rectified_detected=len(caught_rect),
                   difference=len(caught_rect) - len(caught_axis), criterion_met=len(caught_rect) - len(caught_axis) >= 1 and not [i for i in caught_axis if i not in caught_rect],
                   median_score_change=float(np.median([flat[i] - axis[i] for i in DEFECT])),
                   new_errors=[i for i in caught_axis if i not in caught_rect], fp='not_measurable_no_normal_faces',
                   axis_scores=axis, rectified_scores=flat, unjudgeable_scores={i: dict(axis=axis[i], rectified=flat[i]) for i in UNJUDGEABLE},
                   region_scores=regions, device=device, training_calls=0, external_ai_calls=0)
    (out/'corner-rectify-detail.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    print(json.dumps({k: v for k, v in summary.items() if k != 'region_scores'}, ensure_ascii=False), flush=True)
