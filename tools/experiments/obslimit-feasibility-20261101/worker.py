"""Feasibility of whole-face observation-limit (visibility_issues) judgment: ViT-S/14 448 patch tokens mean-pooled over the human-confirmed card box, standardized, L2 logistic regression, group 5-fold CV per side (front/back). Development feasibility only (no band/triage claim, no independent evaluation). Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cv = _load('gcv', 'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
bag, sw = cv.bag, cv.sw
LAM, DRAWS, SEED = 1e-2, 2000, 20261101


def fit_predict(xtr, ytr, xte):
    mu, sd = xtr.mean(0), xtr.std(0) + 1e-6
    a, b = (xtr-mu)/sd, (xte-mu)/sd
    w, bias = torch.zeros(a.shape[1], requires_grad=True), torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([w, bias], max_iter=100, line_search_fn='strong_wolfe')
    y = ytr.float()

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(a @ w + bias, y) + LAM*(w**2).sum()
        loss.backward()
        return loss
    opt.step(closure)
    return (b @ w + bias).sigmoid().detach().tolist()


def auc_ci(rows, scores):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng, vals = random.Random(SEED), []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) > 1:
            vals.append(bag.auc(sub, [scores[i] for i in pick]))
    vals.sort()
    return dict(lo=vals[int(.025*(len(vals)-1))], hi=vals[int(.975*(len(vals)-1))], draws=len(vals))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'obslimit-feasibility-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    pooled = (x*m[..., None]).sum(1)/m.sum(1, keepdim=True)
    fold = cv.fold_of(rows)
    scores, result = [0.]*len(rows), {}
    for side in ('front', 'back'):
        sel = [i for i, r in enumerate(rows) if r['side'] == side]
        for f in range(cv.FOLDS):
            tr = [i for i in sel if fold[rows[i]['group']] != f]
            te = [i for i in sel if fold[rows[i]['group']] == f]
            if not te or len({rows[i]['target'] for i in tr}) < 2:
                continue
            for i, s in zip(te, fit_predict(pooled[tr], torch.tensor([rows[i]['target'] for i in tr]), pooled[te])):
                scores[i] = s
        sub = [rows[i] for i in sel]
        sc = [scores[i] for i in sel]
        result[side] = dict(rows=len(sub), positive=sum(r['target'] for r in sub), groups=len({r['group'] for r in sub}), auc=bag.auc(sub, sc), bootstrap=auc_ci(sub, sc))
    crit = {s: result[s]['auc'] >= plan['criterion_min_auc'] and result[s]['bootstrap']['lo'] >= plan['criterion_min_auc_lower'] for s in result}
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, sides=result, device=device, typed_point_response='not_evaluated', training_calls=2*cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
