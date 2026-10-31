"""Labeling aid (not a performance experiment): train the control head on labeled training rows only and write phone-page presets for unlabeled faces.
Only confident areas are filled (score >= 0.6 defect, <= 0.4 normal); the card box stays unconfirmed. Never use for independent holdout labels."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
DEFECT, NORMAL = 0.6, 0.4
AREAS = ('upper_left', 'upper_center', 'upper_right', 'middle_left', 'middle_right', 'lower_left', 'lower_center', 'lower_right')


def load(path):
    spec = importlib.util.spec_from_file_location('m', ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def labeled_rows(sw, imported_files):
    rows = []
    for f in imported_files:
        for line in Path(f).read_text().splitlines():
            r = json.loads(line)
            a = r['side_annotations']['back']
            if a.get('box_reviewed') is not True:
                continue
            sha = hashlib.sha256(Path(a['image']).read_bytes()).hexdigest()
            for area, v in a['region_labels'].items():
                if v.get('edge_defect') is not None:
                    rows.append(dict(id=f"{r['id']}/back/edge/{area}", group=r['id'], split='train', image=a['image'], image_sha256=sha, area=area,
                                     target=int(v['edge_defect']), box=sw.region_box(a['box'], area)))
    return rows


def main(review_jsonl, out_answers, *imported_files):
    sw = load('tools/experiments/edge-back-source-weight-20261030/worker.py')
    coverage = json.loads((ROOT/'artifacts/development-manifest-20261031o/coverage.json').read_text())
    train = sw.edge_rows(coverage) + labeled_rows(sw, imported_files)
    targets, faces = [], []
    for line in Path(review_jsonl).read_text().splitlines():
        r = json.loads(line)
        a = r['side_annotations']['back']
        faces.append((r['id'], a['box']))
        for area in AREAS:
            targets.append(dict(id=f"{r['id']}/back/edge/{area}", group=r['id'], split='test', image=a['image'], image_sha256=hashlib.sha256(Path(a['image']).read_bytes()).hexdigest(),
                                area=area, target=0, box=sw.region_box(a['box'], area)))  # target unused for scoring
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/'artifacts/torch-cache/hub/facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8'), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/'artifacts/torch-cache/hub/checkpoints/dinov2_vits14_pretrain.pth', map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, train, device)
    coef, bias, _ = sw.fit(x, m, train)
    del x, m
    xt, mt = sw.features(body, targets, device)
    scores = sw.score(xt, mt, coef, bias)
    by = {t['id']: s for t, s in zip(targets, scores)}
    lines, filled = [], 0
    for rid, box in faces:
        states = []
        for area in AREAS:
            s = by[f'{rid}/back/edge/{area}']
            state = '결함' if s >= DEFECT else '정상' if s <= NORMAL else '미확인'
            filled += state != '미확인'
            states.append(f'{area}:{state}')
        lines.append(f"{rid}/back=미확인;box:{','.join(f'{v:.4f}' for v in box)};" + ';'.join(states))
    Path(out_answers).write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(train_rows=len(train), faces=len(faces), areas=len(targets), filled=filled, device=device)))


if __name__ == '__main__':
    main(*sys.argv[1:])
