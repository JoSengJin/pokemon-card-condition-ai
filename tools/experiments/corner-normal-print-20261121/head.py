"""Existing card-ranking fit plus a penalty on confirmed normal print."""
import importlib.util
import math
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
source = ROOT / 'tools/experiments/corner-card-ranking-20261121/head.py'
spec = importlib.util.spec_from_file_location('rank_head', source)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
corner, pair = frozen.corner, frozen.pair


def print_penalty(logits, mask):
    count = mask.sum(1)
    selected = count > 0
    values = F.softplus(logits).masked_fill(~mask, 0).sum(1)
    return (values[selected] / count[selected]).mean()


def fit(x, masks, rows, card_weight, print_mask, print_weight):
    """Keep the card-ranking objective and add one confirmed-print loss."""
    y, mass = corner.guarded_masses(rows)
    pairs = pair.photo_pairs(rows)
    cards = frozen.card_indices(rows)
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
        base = sum(mass[i]*pair.detail_bag_loss(logits[i], int(y[i]), valid[i], None, 'max_bound') for i in range(len(x))) + .5*pair.PENALTY*coef.square().sum()
        s = pair.TAU*torch.logsumexp(logits.masked_fill(~valid, -torch.inf)/pair.TAU, 1)
        within = torch.stack([F.softplus(-(s[p][:, None] - s[n][None, :])).mean() for p, n in pairs]).mean()
        loss = base + pair.LAMBDA*within + card_weight*frozen.card_pair_loss(s, *cards) + print_weight*print_penalty(logits, print_mask)
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
