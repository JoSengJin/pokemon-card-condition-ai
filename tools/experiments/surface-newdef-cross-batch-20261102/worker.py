"""Cross-batch check: train on one source batch, evaluate on the other (y,z,aa <-> ad,ae,af); development only. Based on the pooled new-definition back-surface zones (intakes y,z,aa + ad,ae,af). Candidate B = same head recipe trained on pooled new-definition labels (group 5-fold out-of-fold); control = frozen candidate A scores (trained once on the 411 old-definition zones, stored from the two earlier holdout runs). Paired by photo group. Development only (these photos were already used once as holdouts)."""
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


others = _load('others', 'tools/experiments/edge-back-triage-others-20261101/worker.py')
cv, bag, sw = others.cv, others.bag, others.sw
DRAWS, SEED = 2000, 20261102


def fit_pool(x, masks, rows):
    """sw.fit with the source rebalancing guarded: the original multiplies ebay masses by non-ebay/ebay mass, which is 0/0 when every training group is eBay (the pooled new-definition data)."""
    y = torch.tensor([r['target'] for r in rows])
    count = {}
    for r in rows:
        count[r['group']] = count.get(r['group'], 0) + 1
    mass = torch.tensor([1/count[r['group']] for r in rows])
    ebay = torch.tensor([r['group'].startswith('ebay') for r in rows])
    if (~ebay).any() and ebay.any():
        mass[ebay] *= mass[~ebay].sum()/mass[ebay].sum()
    mass[y == 1] *= mass[y == 0].sum()/mass[y == 1].sum()
    return sw.fit_detail_head(x, masks, y, torch.full((len(rows),), -1, dtype=torch.long), mass, penalty=1., normal_reduction='max_bound')


def paired_bootstrap(rows, new, old):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) < 2:
            continue
        diffs.append(bag.auc(sub, [new[i] for i in pick]) - bag.auc(sub, [old[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-newdef-cross-batch-20261102':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    a_scores = json.loads((ROOT/plan['candidate_a_scores']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows'] or len(a_scores) != len(rows):
        raise ValueError('Frozen rows differ')
    src = ['new' if 'intake-20261102' in r['image'] else 'old' for r in rows]
    if src.count('old') != plan['expected_old'] or src.count('new') != plan['expected_new']:
        raise ValueError('Source split differs')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    scores = [0.]*len(rows)
    res = {}
    for train_src, test_src in (('old', 'new'), ('new', 'old')):
        tr = [i for i, s in enumerate(src) if s == train_src]
        te = [i for i, s in enumerate(src) if s == test_src]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in te])
        t = torch.tensor(tr)
        coef, bias, _ = fit_pool(x[t], m[t], [rows[i] for i in tr])
        h = torch.tensor(te)
        for i, s in zip(te, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
        sub = [rows[i] for i in te]
        b, a = [scores[i] for i in te], [a_scores[i] for i in te]
        boot = paired_bootstrap(sub, b, a)
        res[f'{train_src}->{test_src}'] = dict(rows=len(sub), positive=sum(r['target'] for r in sub), auc_b=bag.auc(sub, b), auc_a=bag.auc(sub, a), diff=bag.auc(sub, b)-bag.auc(sub, a), diff_bootstrap=boot,
                                              criterion=bag.auc(sub, b)-bag.auc(sub, a) >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, candidate_a_scores=a_scores), allow_nan=False))
    summary = dict(criterion_met=all(v['criterion'] for v in res.values()), directions=res, device=device, typed_point_response='not_evaluated', training_calls=2, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
