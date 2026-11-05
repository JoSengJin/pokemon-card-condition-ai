"""Back-edge pair head with the four side-middle areas cropped to the outer 40% band next to the card edge; corner areas unchanged. Same data, head and seeds. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('l8w', ROOT/'tools/experiments/edge-back-layer8-pair-20261031/worker.py')
l8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l8)
vs, pb, pair, bag, sw = l8.vs, l8.pb, l8.pair, l8.bag, l8.sw
BAND = 0.4  # fixed before any score was seen


def band_box(box, area):
    """Keep only the outer BAND of the cell that touches the card edge (side-middle areas); other areas keep the full cell."""
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    if area == 'middle_left':
        right = left + BAND*w
    elif area == 'middle_right':
        left = right - BAND*w
    elif area == 'upper_center':
        bottom = top + BAND*h
    elif area == 'lower_center':
        top = bottom - BAND*h
    return [left, top, right, bottom]


def by_area(val, scores):
    groups = defaultdict(list)
    for r, s in zip(val, scores):
        groups[r['area']].append((r['target'], s))
    out = {}
    for area, items in sorted(groups.items()):
        pos, neg = [s for t, s in items if t], [s for t, s in items if not t]
        out[area] = dict(n=len(items), positive=len(pos), auc=sum((p > n) + .5*(p == n) for p in pos for n in neg)/len(pos)/len(neg) if pos and neg else None)
    return out


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-outer-band-'):
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
    band_train = [dict(r, box=band_box(r['box'], r['area'])) for r in train]
    band_val = [dict(r, box=band_box(r['box'], r['area'])) for r in val]
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = sw.features(body, band_train, device)
    xv, mv = sw.features(body, band_val, device)
    coef, bias, conv = pair.fit_pair(xt, mt, train)
    full = sw.score(xv, mv, coef, bias)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=full), allow_nan=False))
    heads, redraws = pb.pair_heads(xt, mt, train, xv, mv)
    spread = vs.spread(val, heads)
    ens = torch.tensor(heads).mean(0).tolist()
    summary = dict(band_bootstrap=spread, criterion_min_mean_auc=plan['criterion_min_mean_auc'], criterion_met=spread['mean'] >= plan['criterion_min_mean_auc'],
                   full_cell_pair_bootstrap_mean=.7013875365141188, full_cell_pair_bootstrap_std=.04740107906933811,
                   full=dict(auc=bag.auc(val, full), same_photo=bag.auc(val, full, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, full)),
                             fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, full)), by_area=by_area(val, full)),
                   ensemble=dict(auc=bag.auc(val, ens), same_photo=bag.auc(val, ens, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, ens)),
                                 fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, ens)), by_area=by_area(val, ens)),
                   head3_auc=bag.auc(val, ref['before_scores']), val_positive=sum(r['target'] for r in val), val_normal=sum(1 - r['target'] for r in val),
                   band=BAND, redraws=redraws, pair_convergence=conv, train_units=len(train), device=device, separation=separation,
                   typed_point_response='not_evaluated', training_calls=1 + bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
