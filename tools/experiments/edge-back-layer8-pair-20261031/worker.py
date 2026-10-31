"""Back-edge pair head on DINOv2 layer-8 tokens (index 7, normed) instead of the last layer; same data, head, seeds. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vs = _load('vsw', 'tools/experiments/edge-back-pair-vs-control-m-20261031/worker.py')
pb, pair, bag, sw = vs.pb, vs.pair, vs.bag, vs.sw
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import view_tensors  # noqa: E402

LAYER = 7  # 8th of 12 blocks, fixed before any score was seen


def layer_features(body, rows, device):
    """Same views, masks and token shape as sw.features, but tokens come from block LAYER (normed) instead of the last layer."""
    cache, done = {}, {}
    for r in rows:
        cache.setdefault(r['image'], []).append(r)
    with torch.inference_mode():
        for path, items in cache.items():
            for r, tensor in zip(items, view_tensors(path, [i['box'] for i in items], 448)):
                z = body.get_intermediate_layers(tensor[None].to(device), n=[LAYER], norm=True)[0].cpu()[0]
                if z.shape != (1024, 384) or not torch.isfinite(z).all():
                    raise ValueError('Unexpected feature tensor')
                m = physical_pixel_mask(path, r['box'], halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
                done[r['id']] = (z, m)
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-layer8-pair-'):
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
    xt, mt = layer_features(body, train, device)
    xv, mv = layer_features(body, val, device)
    coef, bias, conv = pair.fit_pair(xt, mt, train)
    full = sw.score(xv, mv, coef, bias)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=full), allow_nan=False))
    heads, redraws = pb.pair_heads(xt, mt, train, xv, mv)
    spread = vs.spread(val, heads)
    ens = torch.tensor(heads).mean(0).tolist()
    summary = dict(pair_bootstrap=spread, criterion_min_mean_auc=plan['criterion_min_mean_auc'], criterion_met=spread['mean'] >= plan['criterion_min_mean_auc'],
                   last_layer_pair_bootstrap_mean=.7013875365141188, last_layer_pair_bootstrap_std=.04740107906933811,
                   full=dict(auc=bag.auc(val, full), same_photo=bag.auc(val, full, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, full)),
                             fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, full))),
                   ensemble=dict(auc=bag.auc(val, ens), same_photo=bag.auc(val, ens, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, ens)),
                                 fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, ens))),
                   head3_auc=bag.auc(val, ref['before_scores']), val_positive=sum(r['target'] for r in val), val_normal=sum(1 - r['target'] for r in val),
                   redraws=redraws, pair_convergence=conv, layer=LAYER, train_units=len(train), device=device, separation=separation,
                   typed_point_response='not_evaluated', training_calls=1 + bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
