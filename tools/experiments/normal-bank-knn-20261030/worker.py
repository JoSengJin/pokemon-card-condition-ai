"""Normal-patch-bank kNN score for the back-edge units. Only the scoring method changes; no learned head, no val-tuned threshold."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
_spec = importlib.util.spec_from_file_location('sw', ROOT/'artifacts/edge-back-source-weight-20261030/worker.py')
sw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sw)
PERCENTILE = .9  # fixed before any val score was seen


def patch_bank(x, masks, rows, keep=None):
    """L2-normalized valid patches of normal units; keep optionally restricts to a set of row indices."""
    take = [i for i, r in enumerate(rows) if r['target'] == 0 and (keep is None or i in keep)]
    xs = [torch.nn.functional.normalize(x[i][masks[i]].float(), dim=1) for i in take]
    return torch.cat(xs)


def unit_scores(x, masks, bank, device, chunk=2048):
    """Per unit: max over valid patches of (1 - best cosine similarity to the bank)."""
    bank = bank.to(device)
    out = []
    for z, m in zip(x, masks):
        q = torch.nn.functional.normalize(z[m].float(), dim=1).to(device)
        best = torch.cat([(q[i:i+chunk] @ bank.T).amax(1) for i in range(0, len(q), chunk)])
        out.append(float((1 - best).amax()))
    return out


def leave_group_out(x, masks, rows, device):
    scores = {}
    for g in sorted({r['group'] for r in rows if r['target'] == 0}):
        inside = {i for i, r in enumerate(rows) if r['group'] == g}
        bank = patch_bank(x, masks, rows, keep={i for i in range(len(rows)) if i not in inside})
        for i in inside:
            if rows[i]['target'] == 0:
                scores[i] = unit_scores(x[i:i+1], masks[i:i+1], bank, device)[0]
    return [scores[i] for i in sorted(scores)]


def auc(truth, scores):
    pos = [s for t, s in zip(truth, scores) if t]
    neg = [s for t, s in zip(truth, scores) if not t]
    return sum((p > n) + .5*(p == n) for p in pos for n in neg)/len(pos)/len(neg)


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('normal-bank-knn-'):
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
    logo = leave_group_out(xt, mt, train, device)  # train normals only, never val
    ordered = sorted(logo)
    tau = ordered[min(len(ordered) - 1, int(PERCENTILE*len(ordered)))]
    sigma = float(torch.tensor(logo).std())
    if not sigma > 0:
        raise ValueError('Degenerate leave-group-out score spread')
    xv, mv = sw.features(body, val, device)
    raw = unit_scores(xv, mv, patch_bank(xt, mt, train), device)
    scores = [float(torch.sigmoid(torch.tensor((d - tau)/sigma))) for d in raw]
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    truth = [r['target'] for r in val]
    summary = dict(val_auc=auc(truth, raw), reference_auc=0.804, tau=tau, sigma=sigma, bank_units=sum(r['target'] == 0 for r in train),
                   logo_scores=len(logo), val_fn=sum(t == 1 and s < .5 for t, s in zip(truth, scores)),
                   val_fp=sum(t == 0 and s >= .5 for t, s in zip(truth, scores)), val_positive=sum(truth), val_normal=len(truth) - sum(truth),
                   separation=separation, device=device, training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False), flush=True)
