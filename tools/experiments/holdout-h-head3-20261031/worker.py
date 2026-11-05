"""First evaluation of the frozen 20261030T113857 head on unseen new eBay photos (batch h) with per-area human labels. No training."""
import collections
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

BATCH = 'artifacts/ebay-intake-20261031-h'
RUN = 'artifacts/experiments/20261030T113857-2deb9558'


def holdout_rows():
    """Box-correct faces only; 정상=0, 결함=1, 불가/미확인 skipped (never guessed)."""
    faces = {f['id']: f for f in json.loads((ROOT/BATCH/'back-faces.json').read_text())}
    rows = []
    for line in (ROOT/BATCH/'region-answers.txt').read_text().splitlines():
        if not line.strip():
            continue
        face_id, rest = line.split('=', 1)
        box_answer, *items = [p.strip() for p in rest.split(';')]
        if box_answer != '맞음':
            continue
        for area, label in (item.split(':') for item in items):
            if label in ('정상', '결함'):
                f = faces[face_id]
                rows.append(dict(id=f'{face_id}/back/edge/{area}', group=face_id, split='holdout', image=f['image'], image_sha256=f['sha'],
                                 area=area, target=int(label == '결함'), box=region_box(f['box'], area)))
    return rows


def null_scores(rows, coverage):
    """Reference: train defect rate by area only (no image information)."""
    rate = collections.defaultdict(lambda: [0, 0])
    for u in sw.edge_rows(coverage):
        if u['split'] == 'train':
            rate[u['area']][0] += u['target']
            rate[u['area']][1] += 1
    return [(rate[r['area']][0] + .5)/(rate[r['area']][1] + 1) for r in rows]


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('holdout-h-head3-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = holdout_rows()
    if [dict(r) for r in rows] != ref['rows']:
        raise ValueError('Holdout rows differ from the frozen reference')
    coverage = json.loads((ROOT/plan['coverage']).read_text())
    separation = sw.check_separation(sw.edge_rows(coverage), rows)  # no group or photo shared with train/val
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    head = torch.load(ROOT/RUN/'head.pt', map_location='cpu', weights_only=True)
    x, masks = sw.features(body, rows, device)
    scores = sw.score(x, masks, head['coef'], head['bias'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    truth = [r['target'] for r in rows]
    summary = dict(wp.summarize(rows, scores), null_summary=wp.summarize(rows, ref['before_scores']), separation=separation,
                   fn=sum(t == 1 and s < .5 for t, s in zip(truth, scores)), fp=sum(t == 0 and s >= .5 for t, s in zip(truth, scores)),
                   positive=sum(truth), normal=len(truth) - sum(truth), device=device, training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
