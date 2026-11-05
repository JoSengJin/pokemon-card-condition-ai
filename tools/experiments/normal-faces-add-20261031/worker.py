"""Back-edge head with face-level confirmed-normal eBay faces added to train (8 edge areas each, target 0). Everything else as the 20261030T113857 run."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
_spec = importlib.util.spec_from_file_location('sw', ROOT/'artifacts/edge-back-source-weight-20261030/worker.py')
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)
from card_condition.regions import GLARE_AREAS, region_box  # noqa: E402

EDGE_AREAS = [a for a in GLARE_AREAS if a != 'center']
BATCHES = ('artifacts/ebay-intake-20261030-f', 'artifacts/ebay-intake-20261030-g')


def normal_face_rows():
    """Faces the user confirmed as box-correct AND whole-back-edge normal; a normal face makes all 8 edge areas normal."""
    rows = []
    for batch in BATCHES:
        answers = dict(l.split('=') for l in (ROOT/batch/'back-edge-answers.txt').read_text().split())
        faces = {f['id']: f for f in json.loads((ROOT/batch/'back-faces.json').read_text())}
        for face_id, answer in answers.items():
            if answer != '맞음,정상':
                continue
            f = faces[face_id]
            rows += [dict(id=f'{face_id}/back/edge/{area}', group=face_id, split='train', image=f['image'], image_sha256=f['sha'],
                          area=area, target=0, box=region_box(f['box'], area)) for area in EDGE_AREAS]
    return rows


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('normal-faces-add-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'val']
    extra = normal_face_rows()
    if [len(train), len(val), len(extra)] != plan['expected_denominators']['train_val_extra'] or [dict(r) for r in val] != ref['rows']:
        raise ValueError('Frozen denominator or reference rows changed')
    if len({r['id'] for r in train + extra}) != len(train) + len(extra):
        raise ValueError('Duplicate train unit identity')
    train += extra
    separation = sw.check_separation(train, val)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = sw.features(body, train, device)
    xv, mv = sw.features(body, val, device)
    coef, bias, convergence = sw.fit(xt, mt, train)
    scores = sw.score(xv, mv, coef, bias)
    torch.save(dict(coef=coef, bias=bias, train_ids=[r['id'] for r in train]), out/'head.pt')
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    truth = [r['target'] for r in val]
    pos = [s for t, s in zip(truth, scores) if t]; neg = [s for t, s in zip(truth, scores) if not t]
    summary = dict(val_auc=sum((p > n) + .5*(p == n) for p in pos for n in neg)/len(pos)/len(neg), reference_auc=0.804,
                   val_fn=sum(t == 1 and s < .5 for t, s in zip(truth, scores)), val_fp=sum(t == 0 and s >= .5 for t, s in zip(truth, scores)),
                   val_positive=len(pos), val_normal=len(neg), train_units=len(train), added_normal_units=len(extra),
                   convergence=convergence, separation=separation, device=device, training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
