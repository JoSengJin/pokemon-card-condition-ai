"""H2 (2026-11-20): is local evidence (partial reflection / blur / occlusion) diluted by averaging 1024 patches? Same protocol as the whole-photo F measurement (fit once on the 267 dev rows, score the 219 eBay back rows, development data since 2026-11-20). Single changed variable: pooling (masked patch mean -> masked per-dimension mean of the top-k patch values, k fixed in plan). Same DINOv2 vits14 448 whole-photo tokens, same standardized L2 logistic. Paired comparison against the frozen F scores of experiment 20261119T150351-39395830. Development only, not independent. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
HYPOTHESIS = 'obslimit-topk-h2-20261120'
WHOLE = [0., 0., 1., 1.]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h3 = _load('obsruleh3', 'artifacts/obslimit-rule-h3-20261120/worker.py')
h1, ms, bag, ps, sw = h3.h1, h3.ms, h3.bag, h3.ps, h3.h1.sw


def topk_pooled(body, rows, device, k):
    x, m = sw.features(body, rows, device)
    if int(m.sum(1).min()) < k:
        raise ValueError('Fewer valid patches than k')
    return x.masked_fill(~m[..., None], -torch.inf).topk(k, dim=1).values.mean(1)


def check_inputs(plan, ref):
    if plan['hypothesis_id'] != HYPOTHESIS:
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    train = json.loads((ROOT/plan['train_rows']).read_text())
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows'] or len(train) != plan['expected_train_rows']:
        raise ValueError('Frozen rows differ')
    if sum(r['target'] for r in rows) != plan['expected_positives'] or any(r['box'] != WHOLE for r in rows):
        raise ValueError('Eval denominators or input box differ')
    return train, rows


def verdict(delta, lo, crit):
    if delta >= crit['min_delta_auc'] and lo > crit['min_delta_lower_exclusive']:
        return 'pooling_loss_supported'
    return 'pooling_loss_not_supported'


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    train, rows = check_inputs(plan, ref)
    h3.check_separation(train, rows, plan['expected_train_ebay_groups'])
    f_scores = ref['before_scores']
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    k = plan['top_k']
    xtr = topk_pooled(body, [dict(r, box=WHOLE) for r in train], device, k)
    xte = topk_pooled(body, rows, device, k)
    scores = ms.fit_predict(xtr, torch.tensor([r['target'] for r in train]), xte)
    auc_f, auc_t = bag.auc(rows, f_scores), bag.auc(rows, scores)
    delta = ps.paired(rows, f_scores, scores)
    result = verdict(auc_t-auc_f, delta['lo'], plan['criterion'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(verdict=result, criterion_met=result == 'pooling_loss_supported', top_k=k,
                   topk=dict(auc=auc_t, bootstrap=ms.auc_ci(rows, scores), **h1.counts(rows, scores)),
                   f=dict(auc=auc_f, bootstrap=ms.auc_ci(rows, f_scores), **h1.counts(rows, f_scores)),
                   delta_auc=auc_t-auc_f, delta_bootstrap=delta, rows=len(rows), train_rows=len(train), device=device,
                   training_calls=1, external_ai_calls=0, independent=False)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
