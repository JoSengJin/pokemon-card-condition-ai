"""Back-edge head bagging: mean of B heads fit on group-bootstrap resamples of the same train units; scored once on frozen val. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('sw', ROOT/'tools/experiments/edge-back-source-weight-20261030/worker.py')
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)
BAGS = 20
SEED = 20261031
MAX_REDRAWS = 20  # single-class or non-converged resamples are dropped and the next seed is drawn; more than 20 stops the run


def resample(train, seed):
    """Draw train groups with replacement; each copy gets its own group id so every drawn copy keeps full group mass. Returns row indices and new rows."""
    groups = sorted({r['group'] for r in train})
    gen = torch.Generator().manual_seed(seed)
    picks = [groups[i] for i in torch.randint(len(groups), (len(groups),), generator=gen).tolist()]
    index, rows = [], []
    for k, g in enumerate(picks):
        for i, r in enumerate(train):
            if r['group'] == g:
                index.append(i)
                rows.append(dict(r, group=f'{g}#{k}'))
    return index, rows


def bag_scores(xt, mt, train, xv, mv):
    """Fit BAGS heads on seeded resamples that contain both classes and converge; return their val score lists and the number of redraws."""
    heads, redraws, seed = [], 0, SEED
    while len(heads) < BAGS:
        index, rows = resample(train, seed)
        seed += 1
        if len({r['target'] for r in rows}) < 2:
            redraws += 1
            continue
        try:
            coef, bias, _ = sw.fit(xt[index], mt[index], rows)
        except ValueError as error:
            if 'did not converge' not in str(error) or redraws >= MAX_REDRAWS:
                raise
            redraws += 1
            continue
        heads.append(sw.score(xv, mv, coef, bias))
    return heads, redraws


def auc(rows, scores, same_photo=False):
    pos = [(r['image'], s) for r, s in zip(rows, scores) if r['target']]
    neg = [(r['image'], s) for r, s in zip(rows, scores) if not r['target']]
    pairs = [(p, n) for p in pos for n in neg if not same_photo or p[0] == n[0]]
    return sum((p[1] > n[1]) + .5*(p[1] == n[1]) for p, n in pairs)/len(pairs)


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-bagging-'):
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
    heads, redraws = bag_scores(xt, mt, train, xv, mv)
    scores = torch.tensor(heads).mean(0).tolist()
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    single = [auc(val, h) for h in heads]
    mean = sum(single)/len(single)
    summary = dict(val_auc=auc(val, scores), val_auc_same_photo=auc(val, scores, True), single_auc_mean=mean,
                   single_auc_std=(sum((a - mean)**2 for a in single)/(len(single) - 1))**.5, single_auc_min=min(single), single_auc_max=max(single),
                   val_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, scores)), val_positive=sum(r['target'] for r in val),
                   val_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, scores)), val_normal=sum(1 - r['target'] for r in val),
                   reference_auc=auc(val, ref['before_scores']), bags=BAGS, redraws=redraws, seed=SEED, device=device, train_units=len(train),
                   val_units=len(val), separation=separation, typed_point_response='not_evaluated', training_calls=BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
