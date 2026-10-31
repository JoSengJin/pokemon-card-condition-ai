"""Back-edge head with a within-photo pairwise ranking term (defect region > normal region of the same photo); same data as the control. Common-runner only."""
import hashlib
import importlib.util
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('sw', ROOT/'tools/experiments/edge-back-source-weight-20261030/worker.py')
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)
from confounder_head import detail_bag_loss  # noqa: E402  (path added by the source-weight worker)

LAMBDA = 1.0
TAU = 0.1  # smooth maximum temperature for the pair term only (the bag loss keeps the control's hard max)
PENALTY = 1.0


def masses(rows):
    """Same train mass as the control: group-normalized, eBay equal to non-eBay, classes balanced; normalized to sum 1."""
    y = torch.tensor([r['target'] for r in rows])
    count = Counter(r['group'] for r in rows)
    mass = torch.tensor([1/count[r['group']] for r in rows], dtype=torch.float64)
    ebay = torch.tensor([r['group'].startswith('ebay') for r in rows])
    mass[ebay] *= mass[~ebay].sum()/mass[ebay].sum()
    mass[y == 1] *= mass[y == 0].sum()/mass[y == 1].sum()
    return y, mass/mass.sum()


def photo_pairs(rows):
    """Per photo with both classes: (positive indices, normal indices)."""
    by = {}
    for i, r in enumerate(rows):
        by.setdefault(r['image'], ([], []))[0 if r['target'] else 1].append(i)
    return [(torch.tensor(p), torch.tensor(n)) for p, n in by.values() if p and n]


def fit_pair(x, masks, rows):
    """Control objective (mass-weighted max_bound bag loss + L2) plus LAMBDA * photo-balanced mean softplus(-(s_defect - s_normal)) with a smooth max (TAU) for s."""
    y, mass = masses(rows)
    pairs = photo_pairs(rows)
    x, valid = torch.as_tensor(x).to(torch.float64), torch.as_tensor(masks)
    summaries = torch.stack([x[i, valid[i]].mean(0) for i in range(len(x))])
    center = (summaries*mass[:, None]).sum(0)
    x = x - center
    coef = torch.zeros(x.shape[2], dtype=x.dtype, requires_grad=True)
    bias = torch.zeros((), dtype=x.dtype, requires_grad=True)
    optimizer = torch.optim.LBFGS([coef, bias], max_iter=300, tolerance_grad=1e-7, tolerance_change=1e-12, history_size=20, line_search_fn='strong_wolfe')

    def closure():
        optimizer.zero_grad()
        logits = x@coef + bias
        base = sum(mass[i]*detail_bag_loss(logits[i], int(y[i]), valid[i], None, 'max_bound') for i in range(len(x))) + .5*PENALTY*coef.square().sum()
        s = TAU*torch.logsumexp(logits.masked_fill(~valid, -torch.inf)/TAU, 1)
        pair = torch.stack([F.softplus(-(s[p][:, None] - s[n][None, :])).mean() for p, n in pairs]).mean()
        loss = base + LAMBDA*pair
        if not torch.isfinite(loss):
            raise ValueError('Non-finite objective')
        loss.backward()
        return loss
    optimizer.step(closure)
    objective = float(closure().detach())
    gradient = max(float(coef.grad.abs().max()), float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient > 1e-5:
        raise ValueError(f'Pair head did not converge: gradient {gradient:.3e}')
    return coef.detach().float(), (bias.detach() - center@coef.detach()).float(), dict(converged=True, train_objective=objective, max_gradient=gradient, mixed_photos=len(pairs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-same-photo-pair-'):
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
    coef, bias, convergence = fit_pair(xt, mt, train)
    scores = sw.score(xv, mv, coef, bias)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))

    def auc(values, same_photo=False):
        pos = [(r['image'], s) for r, s in zip(val, values) if r['target']]
        neg = [(r['image'], s) for r, s in zip(val, values) if not r['target']]
        pairs = [(p, n) for p in pos for n in neg if not same_photo or p[0] == n[0]]
        return sum((p[1] > n[1]) + .5*(p[1] == n[1]) for p, n in pairs)/len(pairs)
    summary = dict(val_auc=auc(scores), val_auc_same_photo=auc(scores, True), control_auc=auc(ref['before_scores']), control_auc_same_photo=auc(ref['before_scores'], True),
                   val_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, scores)), val_positive=sum(r['target'] for r in val),
                   val_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, scores)), val_normal=sum(1 - r['target'] for r in val),
                   train_units=len(train), lambda_pair=LAMBDA, convergence=convergence, device=device, separation=separation,
                   typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
