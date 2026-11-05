"""Back-edge head on per-photo centered patch features. Only the feature preprocessing changes: subtract the mean valid patch of all units
of the same photo group (label-free). Same data, head, L2, mass, val rows and threshold as the 20261030T113857 run."""
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
_spec = importlib.util.spec_from_file_location('sw', ROOT/'artifacts/edge-back-source-weight-20261030/worker.py')
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)
_wp = importlib.util.spec_from_file_location('wp', ROOT/'tools/within_photo_auc.py')
wp = importlib.util.module_from_spec(_wp)
_wp.loader.exec_module(wp)


def center_by_group(x, masks, rows):
    """x - (mean over all valid patches of every unit in the same group). Uses no label; train and val are centered separately."""
    total, count = defaultdict(lambda: torch.zeros(x.shape[2])), defaultdict(int)
    for z, m, r in zip(x, masks, rows):
        total[r['group']] += z[m].float().sum(0)
        count[r['group']] += int(m.sum())
    mean = {g: total[g]/count[g] for g in total}
    return torch.stack([z.float() - mean[r['group']] for z, r in zip(x, rows)])


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('photo-centered-features-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'val']
    if [len(train), len(val)] != plan['expected_denominators']['train_val'] or [dict(r) for r in val] != ref['rows']:
        raise ValueError('Frozen denominator or reference rows changed')
    separation = sw.check_separation(train, val)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = sw.features(body, train, device)
    xv, mv = sw.features(body, val, device)
    xt, xv = center_by_group(xt, mt, train), center_by_group(xv, mv, val)
    coef, bias, convergence = sw.fit(xt, mt, train)
    scores = sw.score(xv, mv, coef, bias)
    torch.save(dict(coef=coef, bias=bias, train_ids=[r['id'] for r in train]), out/'head.pt')
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    truth = [r['target'] for r in val]
    summary = dict(wp.summarize(val, scores), reference_auc=0.804, reference_within_group_auc=0.798,
                   val_fn=sum(t == 1 and s < .5 for t, s in zip(truth, scores)), val_fp=sum(t == 0 and s >= .5 for t, s in zip(truth, scores)),
                   val_positive=sum(truth), val_normal=len(truth) - sum(truth), convergence=convergence, separation=separation,
                   device=device, training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
