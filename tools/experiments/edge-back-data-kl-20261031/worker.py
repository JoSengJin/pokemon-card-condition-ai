"""Back-edge head 3 recipe retrained on manifest 20261031l (k,l train units added); scored once on the same frozen val. Secondary: bagging spread. Common-runner only."""
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


bag = _load('bagw', 'tools/experiments/edge-back-bagging-20261031/worker.py')
sw = bag.sw

if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-data-kl-'):
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
    coef, bias, convergence = sw.fit(xt, mt, train)
    scores = sw.score(xv, mv, coef, bias)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    heads, redraws = bag.bag_scores(xt, mt, train, xv, mv)
    single = [bag.auc(val, h) for h in heads]
    mean = sum(single)/len(single)
    summary = dict(val_auc=bag.auc(val, scores), val_auc_same_photo=bag.auc(val, scores, True), val_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, scores)),
                   val_positive=sum(r['target'] for r in val), val_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, scores)),
                   val_normal=sum(1 - r['target'] for r in val), reference_auc=bag.auc(val, ref['before_scores']), train_units=len(train),
                   train_positive=sum(r['target'] for r in train), train_ebay=sum(r['group'].startswith('ebay') for r in train), convergence=convergence,
                   bag_single_auc_mean=mean, bag_single_auc_std=(sum((a - mean)**2 for a in single)/(len(single) - 1))**.5, bag_single_auc_min=min(single),
                   bag_single_auc_max=max(single), bag_redraws=redraws, device=device, separation=separation, typed_point_response='not_evaluated',
                   training_calls=1 + bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
