"""Corner-rectify on a new eBay batch (g): 12 defect + 5 normal faces. Same head/areas; only the crop changes. Inference only."""
import importlib.util
import json
import os
from pathlib import Path

import torch

_spec = importlib.util.spec_from_file_location('cr', Path(__file__).resolve().parents[1]/'corner-rectify-20261030/worker.py')
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)
ROOT, RUN = cr.ROOT, cr.RUN
BATCH = 'artifacts/ebay-intake-20261030-g'


def face_sets():
    """Box-correct faces only; truth from the user's edge answer. 불가 is scored but never judged."""
    answers = dict(l.split('=') for l in (ROOT/BATCH/'back-edge-answers.txt').read_text().split())
    judged = {i: {'정상': 0, '결함': 1}[a.split(',')[1]] for i, a in answers.items() if a.startswith('맞음') and a.split(',')[1] in ('정상', '결함')}
    unjudged = [i for i, a in answers.items() if a.startswith('맞음') and a.endswith('불가')]
    return judged, unjudged


def score_pair(body, device, face, corners, coef, bias):
    image = cr.load_image(face['image'])
    a = cr.face_score(body, device, image, face['image'], face['box'], coef, bias)
    r = cr.face_score(body, device, cr.rectify(image, corners), face['image'], [0, 0, 1, 1], coef, bias)
    return max(a.values()), max(r.values()), dict(axis=a, rectified=r)


def setup():
    faces = {f['id']: f for f in json.loads((ROOT/BATCH/'back-faces.json').read_text())}
    corners = cr.load_corners((ROOT/BATCH/'corner-answers.txt').read_text())
    judged, unjudged = face_sets()
    for i in [*judged, *unjudged]:
        if cr.decoded_hash(Path(faces[i]['image']).read_bytes())[0] != faces[i]['sha'] or i not in corners:
            raise ValueError('Photo or corner answer missing/changed: ' + i)
    head = torch.load(ROOT/RUN/'head.pt', map_location='cpu', weights_only=True)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = cr.load_body(json.loads((ROOT/RUN/'plan.json').read_text()), device)
    return faces, corners, judged, unjudged, head, body, device


def reference_rows(faces, judged):
    return [dict(id=i, group=i, split='dev', image=faces[i]['image'], image_sha256=faces[i]['sha'], area='face_max',
                 target=t, box=faces[i]['box']) for i, t in judged.items()]


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('corner-rectify-batch-g-'):
        raise ValueError('Wrong hypothesis')
    faces, corners, judged, unjudged, head, body, device = setup()
    if [r['id'] for r in ref['rows']] != list(judged) or [r['target'] for r in ref['rows']] != list(judged.values()):
        raise ValueError('Reference rows differ from the confirmed faces')
    detail, axis, rect = {}, {}, {}
    for i in [*judged, *unjudged]:
        axis[i], rect[i], detail[i] = score_pair(body, device, faces[i], corners[i], head['coef'], head['bias'])
    if any(abs(axis[i] - s) > 1e-4 for i, s in zip(judged, ref['before_scores'])):
        raise ValueError('Axis-aligned scores differ from the frozen reference; stopping')
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=[rect[i] for i in judged]), allow_nan=False))
    t = lambda s: s >= .5
    summary = dict(defect=sum(judged.values()), normal=len(judged) - sum(judged.values()),
                   axis=dict(fn=sum(judged[i] and not t(axis[i]) for i in judged), fp=sum(not judged[i] and t(axis[i]) for i in judged)),
                   rectified=dict(fn=sum(judged[i] and not t(rect[i]) for i in judged), fp=sum(not judged[i] and t(rect[i]) for i in judged)),
                   unjudged={i: dict(axis=axis[i], rectified=rect[i]) for i in unjudged}, axis_scores=axis, rectified_scores=rect,
                   region_scores=detail, device=device, training_calls=0, external_ai_calls=0)
    (out/'corner-rectify-detail.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    print(json.dumps({k: v for k, v in summary.items() if k != 'region_scores'}, ensure_ascii=False), flush=True)
