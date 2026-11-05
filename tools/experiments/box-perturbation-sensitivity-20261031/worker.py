"""Box-perturbation sensitivity of the frozen 20261030T113857 head 3 on the val 275 back-edge units. Inference only; no training."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sw = _load('sw', 'artifacts/edge-back-source-weight-20261030/worker.py')
wp = _load('wp', 'tools/within_photo_auc.py')
from card_condition.regions import region_box  # noqa: E402

RUN = 'artifacts/experiments/20261030T113857-2deb9558'
PRIMARY = 'widen_0.10'
ARMS = {'identity': ('widen', 0.), 'widen_0.05': ('widen', .05), 'widen_0.10': ('widen', .10), 'widen_0.20': ('widen', .20),
        'shift_0.05_diagonal': ('shift', .05), 'tight_0.03': ('widen', -.03)}
CRITERIA = dict(max_fn=28, max_fp=69, min_auc=0.774)


def perturbed_box(box, kind, f, index):
    """Widen (f<0 shrinks) each side by f of the box size, or shift diagonally by f; always clipped to [0, 1]."""
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    dx = dy = 0.
    if kind == 'shift':
        sx, sy = ((1, 1), (1, -1), (-1, 1), (-1, -1))[index % 4]
        dx, dy, f = sx*f*width, sy*f*height, 0.
    return [min(1., max(0., v)) for v in (left - f*width + dx, top - f*height + dy, right + f*width + dx, bottom + f*height + dy)]


def card_boxes(coverage):
    return {f"{u['card_id']}/back/edge/{u['area']}": u['card_box'] for u in coverage['units']
            if u['label'] == 'edge_defect' and u['side'] == 'back'}


def arm_rows(rows, cards, kind, f):
    """One perturbed card box per photo (same for all its areas), then the usual 3x3 region box."""
    order = {p: i for i, p in enumerate(sorted({r['image'] for r in rows}))}
    return [dict(r, box=region_box(perturbed_box(cards[r['id']], kind, f, order[r['image']]), r['area'])) for r in rows]


def score_arm(body, rows, head, device):
    x, masks = sw.features(body, rows, device)
    return sw.score(x, masks, head['coef'], head['bias'])


def summarize(rows, scores):
    truth = [r['target'] for r in rows]
    return dict(wp.summarize(rows, scores), fn=sum(t == 1 and s < .5 for t, s in zip(truth, scores)),
                fp=sum(t == 0 and s >= .5 for t, s in zip(truth, scores)), positive=sum(truth), normal=len(truth) - sum(truth))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('box-perturbation-sensitivity-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    coverage = json.loads((ROOT/plan['coverage']).read_text())
    rows = [r for r in sw.edge_rows(coverage) if r['split'] == 'val']
    cards = card_boxes(coverage)
    if [dict(r) for r in rows] != ref['rows'] or len(rows) != plan['expected_denominators']['val']:
        raise ValueError('Frozen val rows changed')
    if any(region_box(cards[r['id']], r['area']) != r['box'] for r in rows):
        raise ValueError('Card box mapping does not reproduce the frozen region boxes')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    head = torch.load(ROOT/RUN/'head.pt', map_location='cpu', weights_only=True)
    scores = {name: score_arm(body, arm_rows(rows, cards, *arm), head, device) for name, arm in ARMS.items()}
    drift = max(abs(a - b) for a, b in zip(scores['identity'], ref['before_scores']))
    if drift > 1e-4:
        raise ValueError(f'Unperturbed rescoring differs from the frozen scores by {drift}; stopping before any comparison')
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores[PRIMARY]), allow_nan=False))
    arms = {name: summarize(rows, s) for name, s in scores.items()}
    primary = arms[PRIMARY]
    met = primary['fn'] <= CRITERIA['max_fn'] and primary['fp'] <= CRITERIA['max_fp'] and primary['overall_auc'] >= CRITERIA['min_auc']
    summary = dict(primary_arm=PRIMARY, criteria=CRITERIA, criterion_met=met, identity_drift=drift, arms=arms, device=device,
                   training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: (v if k != 'arms' else {n: {x: a[x] for x in ('overall_auc', 'within_group_auc', 'fn', 'fp')} for n, a in v.items()}) for k, v in summary.items()},
                     ensure_ascii=False, default=float), flush=True)
