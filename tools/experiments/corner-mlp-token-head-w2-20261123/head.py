"""W2 token scorer: hidden-1-layer MLP (width 64, no dropout) replacing the linear token scorer of the corner pair recipe. Objective, masses, pair term, lambda, tau, penalty are the control's (fit_pair)."""
import math
from functools import partial

import torch
from torch.nn import functional as F

LAMBDA, TAU, PENALTY, HIDDEN, SEED, MAX_ITER, GRAD_TOL = 1.0, .1, 1.0, 64, 20261123, 300, 1e-4


def mlp_logits(x, p):
    return torch.relu(x@p[0] + p[1])@p[2] + p[3]


def step(optimizer, p, x, valid, y, mass, pairs, bag_loss):
    """One objective evaluation (LBFGS closure): control's mass-weighted max_bound bag loss + L2 on weights + LAMBDA * same-photo pair term."""
    optimizer.zero_grad()
    logits = mlp_logits(x, p)
    base = sum(mass[i]*bag_loss(logits[i], int(y[i]), valid[i], None, 'max_bound') for i in range(len(x))) + .5*PENALTY*(p[0].square().sum() + p[2].square().sum())
    s = TAU*torch.logsumexp(logits.masked_fill(~valid, -torch.inf)/TAU, 1)
    pair = torch.stack([F.softplus(-(s[a][:, None] - s[b][None, :])).mean() for a, b in pairs]).mean()
    loss = base + LAMBDA*pair
    if not torch.isfinite(loss):
        raise ValueError('Non-finite objective')
    loss.backward()
    return loss


def fit_mlp(x, masks, rows, masses, photo_pairs, bag_loss):
    y, mass = masses(rows)
    pairs = photo_pairs(rows)
    x, valid = torch.as_tensor(x).to(torch.float64), torch.as_tensor(masks)
    center = (torch.stack([x[i, valid[i]].mean(0) for i in range(len(x))])*mass[:, None]).sum(0)
    x = x - center
    g = torch.Generator().manual_seed(SEED)
    d = x.shape[2]
    p = [(torch.randn(d, HIDDEN, generator=g, dtype=x.dtype)/math.sqrt(d)).requires_grad_(), torch.zeros(HIDDEN, dtype=x.dtype, requires_grad=True),
         (.1*torch.randn(HIDDEN, generator=g, dtype=x.dtype)/math.sqrt(HIDDEN)).requires_grad_(), torch.zeros((), dtype=x.dtype, requires_grad=True)]
    optimizer = torch.optim.LBFGS(p, max_iter=MAX_ITER, tolerance_grad=1e-7, tolerance_change=1e-12, history_size=20, line_search_fn='strong_wolfe')
    closure = partial(step, optimizer, p, x, valid, y, mass, pairs, bag_loss)
    optimizer.step(closure)
    objective = float(closure().detach())
    gradient = max(float(q.grad.abs().max()) for q in p)
    if not math.isfinite(gradient) or gradient > GRAD_TOL:
        raise ValueError(f'MLP head did not converge: gradient {gradient:.3e}')
    return dict(params=[q.detach().float() for q in p], center=center.float(), convergence=dict(converged=True, train_objective=objective, max_gradient=gradient, mixed_photos=len(pairs)))


def score_mlp(x, masks, fit):
    logits = mlp_logits(torch.as_tensor(x) - fit['center'], fit['params'])
    return logits.masked_fill(~masks, -torch.inf).amax(1).sigmoid().tolist()
