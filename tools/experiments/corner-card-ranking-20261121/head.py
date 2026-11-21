"""Candidate E's linear head with a cross-card ranking term during training."""
import importlib.util
import math
from collections import defaultdict
from pathlib import Path

import torch
from torch.nn import functional as F
from torch.nn.utils.rnn import pad_sequence

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('mlp_template', ROOT / 'tools/experiments/corner-mlp-head-20261121/worker.py')
template = importlib.util.module_from_spec(spec)
spec.loader.exec_module(template)
corner = template.corner
pair = corner.pair


def card_indices(rows):
    defects, normals = defaultdict(list), defaultdict(list)
    for i, row in enumerate(rows):
        (defects if row['target'] else normals)[row['group']].append(i)
    positive = pad_sequence([torch.tensor(ids) for ids in defects.values()], batch_first=True, padding_value=-1)
    negative = pad_sequence([torch.tensor(ids) for g, ids in normals.items() if g not in defects],
                            batch_first=True, padding_value=-1)
    return positive, negative


def card_scores(scores, indices):
    valid = indices >= 0
    selected = scores[indices].masked_fill(~valid, -torch.inf)
    return pair.TAU * (torch.logsumexp(selected / pair.TAU, dim=1) - valid.sum(dim=1).log())


def card_pair_loss(scores, positive, negative):
    defect = card_scores(scores, positive)
    normal = card_scores(scores, negative)
    return F.softplus(normal[None, :] - defect[:, None]).mean()


def fit(x, masks, rows, weight):
    """Keep Candidate E’s optimizer and add one cross-card loss."""
    y, mass = corner.guarded_masses(rows)
    pairs = pair.photo_pairs(rows)
    cards = card_indices(rows)
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
        loss = base + pair.LAMBDA*within + weight*card_pair_loss(s, *cards)
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

