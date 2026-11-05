"""Robustness of the within-photo pair term: 20 group-bootstrap heads with the pair term vs the control spread; scored once on frozen val. Common-runner only."""
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


pair = _load('pairw', 'tools/experiments/edge-back-same-photo-pair-20261031/worker.py')
bag = _load('bagw', 'tools/experiments/edge-back-bagging-20261031/worker.py')
sw = pair.sw
MAX_REDRAWS = 20


def pair_heads(xt, mt, train, xv, mv):
    """BAGS seeded group resamples; each copy keeps its own group and its own photo key so pair terms stay per copy. Non-converged draws are dropped."""
    heads, redraws, seed = [], 0, bag.SEED
    while len(heads) < bag.BAGS:
        index, rows = bag.resample(train, seed)
        seed += 1
        rows = [dict(r, image=f"{r['image']}#{r['group']}") for r in rows]
        if len({r['target'] for r in rows}) < 2 or not pair.photo_pairs(rows):
            redraws += 1
            continue
        try:
            coef, bias, _ = pair.fit_pair(xt[index], mt[index], rows)
        except ValueError as error:
            if 'did not converge' not in str(error) or redraws >= MAX_REDRAWS:
                raise
            redraws += 1
            continue
        heads.append(sw.score(xv, mv, coef, bias))
    return heads, redraws


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-pair-bagging-'):
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
    heads, redraws = pair_heads(xt, mt, train, xv, mv)
    scores = torch.tensor(heads).mean(0).tolist()
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    single = [bag.auc(val, h) for h in heads]
    same = [bag.auc(val, h, True) for h in heads]
    mean = sum(single)/len(single)
    summary = dict(single_auc_mean=mean, single_auc_std=(sum((a - mean)**2 for a in single)/(len(single) - 1))**.5, single_auc_min=min(single), single_auc_max=max(single),
                   single_same_photo_mean=sum(same)/len(same), single_auc_below_half=sum(a < .5 for a in single), criterion_min_mean_auc=plan['criterion_min_mean_auc'],
                   criterion_met=mean >= plan['criterion_min_mean_auc'], ensemble_auc=bag.auc(val, scores), ensemble_auc_same_photo=bag.auc(val, scores, True),
                   ensemble_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, scores)), ensemble_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, scores)),
                   val_positive=sum(r['target'] for r in val), val_normal=sum(1 - r['target'] for r in val), control_single_auc_mean=.6228984096072704,
                   control_single_auc_std=.16385870353398654, redraws=redraws, bags=bag.BAGS, seed=bag.SEED, device=device, train_units=len(train),
                   separation=separation, typed_point_response='not_evaluated', training_calls=bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
