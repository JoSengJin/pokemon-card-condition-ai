"""Score-level fusion of two pair heads (last-layer and layer-8 tokens) fit on the same group resamples; scored once on frozen val. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('l8w', ROOT/'tools/experiments/edge-back-layer8-pair-20261031/worker.py')
l8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l8)
vs, pb, pair, bag, sw = l8.vs, l8.pb, l8.pair, l8.bag, l8.sw
MAX_REDRAWS = 20


def fuse_heads(last, l8x, train, val_last, val_l8):
    """Per seed, fit one pair head per feature set on the same resample and average their val probabilities. Redraw when either fails."""
    heads, redraws, seed = [], 0, bag.SEED
    while len(heads) < bag.BAGS:
        index, rows = bag.resample(train, seed)
        seed += 1
        rows = [dict(r, image=f"{r['image']}#{r['group']}") for r in rows]
        if len({r['target'] for r in rows}) < 2 or not pair.photo_pairs(rows):
            redraws += 1
            continue
        try:
            parts = [pair.fit_pair(x[index], m[index], rows) for x, m in zip((last[0], l8x[0]), (last[1], l8x[1]))]
        except ValueError as error:
            if 'did not converge' not in str(error) or redraws >= MAX_REDRAWS:
                raise
            redraws += 1
            continue
        scores = [sw.score(v[0], v[1], c, b) for v, (c, b, _) in zip((val_last, val_l8), parts)]
        heads.append(torch.tensor(scores).mean(0).tolist())
    return heads, redraws


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-layer-fusion-'):
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
    tr_last, va_last = sw.features(body, train, device), sw.features(body, val, device)
    tr_l8, va_l8 = l8.layer_features(body, train, device), l8.layer_features(body, val, device)
    full_parts = [pair.fit_pair(x, m, train) for x, m in (tr_last, tr_l8)]
    full = torch.tensor([sw.score(v[0], v[1], c, b) for v, (c, b, _) in zip((va_last, va_l8), full_parts)]).mean(0).tolist()
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=full), allow_nan=False))
    heads, redraws = fuse_heads(tr_last, tr_l8, train, va_last, va_l8)
    spread = vs.spread(val, heads)
    ens = torch.tensor(heads).mean(0).tolist()
    summary = dict(fused_bootstrap=spread, criterion_min_mean_auc=plan['criterion_min_mean_auc'], criterion_met=spread['mean'] >= plan['criterion_min_mean_auc'],
                   last_layer_pair_bootstrap_mean=.7013875365141188, layer8_pair_bootstrap_mean=.6657538136968516,
                   full=dict(auc=bag.auc(val, full), same_photo=bag.auc(val, full, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, full)),
                             fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, full))),
                   ensemble=dict(auc=bag.auc(val, ens), same_photo=bag.auc(val, ens, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, ens)),
                                 fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, ens))),
                   head3_auc=bag.auc(val, ref['before_scores']), val_positive=sum(r['target'] for r in val), val_normal=sum(1 - r['target'] for r in val),
                   redraws=redraws, train_units=len(train), device=device, separation=separation, typed_point_response='not_evaluated',
                   training_calls=2 + 2*bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
