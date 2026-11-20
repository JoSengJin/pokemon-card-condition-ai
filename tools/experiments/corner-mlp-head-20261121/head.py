"""Back-corner token head for the MLP experiment: candidate E's objective (mass-weighted max_bound bag loss + L2 + photo-balanced same-photo pair ranking term, LAMBDA from the pair recipe) with a swappable token scorer. 'linear' reproduces pair.fit_pair (checked by a test); 'mlp' is one tanh hidden layer. Only the scorer differs. Common-runner only."""
import importlib.util
import math
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('corner', ROOT/'tools/experiments/corner-same-photo-pair-cv-20261102/worker.py')
corner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corner)
pair = corner.pair
HIDDEN, MAX_ITER, PENALIZED = 64, 1000, {'linear': ('w',), 'mlp': ('w1', 'w2')}


def linear_logits(x, p):
    return x@p['w'] + p['b']


def mlp_logits(x, p):
    return torch.tanh(x@p['w1'] + p['b1'])@p['w2'] + p['b2']


def init_params(kind, dim, seed):
    """Linear: zeros (the control's start). MLP: nn.Linear-style uniform first layer from a seeded generator, zero output layer."""
    leaf = lambda t: t.to(torch.float64).requires_grad_()
    if kind == 'linear':
        return dict(w=leaf(torch.zeros(dim)), b=leaf(torch.zeros(())))
    g = torch.Generator().manual_seed(seed)
    w1 = (torch.rand(dim, HIDDEN, generator=g)*2 - 1)/math.sqrt(dim)
    return dict(w1=leaf(w1), b1=leaf(torch.zeros(HIDDEN)), w2=leaf(torch.zeros(HIDDEN)), b2=leaf(torch.zeros(())))


def fit_head(x, masks, rows, kind, seed, max_iter):
    """LBFGS fit of pair.fit_pair's objective with the chosen scorer; raises when max |gradient| > 1e-5 (no retries)."""
    logits_fn = dict(linear=linear_logits, mlp=mlp_logits)[kind]
    y, mass = corner.guarded_masses(rows)
    pairs = pair.photo_pairs(rows)
    x, valid = torch.as_tensor(x).to(torch.float64), torch.as_tensor(masks)
    center = (torch.stack([x[i, valid[i]].mean(0) for i in range(len(x))])*mass[:, None]).sum(0)
    x, params = x - center, init_params(kind, x.shape[2], seed)
    optimizer = torch.optim.LBFGS(list(params.values()), max_iter=max_iter, tolerance_grad=1e-7, tolerance_change=1e-12, history_size=20, line_search_fn='strong_wolfe')

    def closure():
        optimizer.zero_grad()
        logits = logits_fn(x, params)
        base = sum(mass[i]*pair.detail_bag_loss(logits[i], int(y[i]), valid[i], None, 'max_bound') for i in range(len(x))) + .5*pair.PENALTY*sum(params[k].square().sum() for k in PENALIZED[kind])
        s = pair.TAU*torch.logsumexp(logits.masked_fill(~valid, -torch.inf)/pair.TAU, 1)
        ranking = torch.stack([F.softplus(-(s[p][:, None] - s[n][None, :])).mean() for p, n in pairs]).mean()
        loss = base + pair.LAMBDA*ranking
        if not torch.isfinite(loss):
            raise ValueError('Non-finite objective')
        loss.backward()
        return loss
    optimizer.step(closure)
    objective = float(closure().detach())
    gradient = max(float(p.grad.abs().max()) for p in params.values())
    if not math.isfinite(gradient) or gradient > 1e-5:
        raise ValueError(f'{kind} head did not converge: gradient {gradient:.3e}')
    return {k: v.detach() for k, v in params.items()}, center, dict(converged=True, train_objective=objective, max_gradient=gradient, mixed_photos=len(pairs))


def score_head(x, masks, fitted, kind):
    """Photo-zone score = sigmoid of the maximum token logit over valid tokens."""
    params, center, _ = fitted
    logits = dict(linear=linear_logits, mlp=mlp_logits)[kind](torch.as_tensor(x).to(torch.float64) - center, params)
    return logits.masked_fill(~torch.as_tensor(masks), -torch.inf).amax(1).sigmoid().tolist()
