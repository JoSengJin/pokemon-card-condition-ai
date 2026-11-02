"""Layer-8 tokens (index 7, normed) instead of the last layer, same pooled 1791 zones, head, folds, seeds; control = last-layer out-of-fold scores of the earlier pooled run. Development CV. Based on: all new-definition back-surface zones (y,z,aa,ad,ae,af + ag,ah,ai = 1791 zones). Candidate C = out-of-fold on the larger pool; control = frozen candidate B scores (B-OOF on the first 1190, B single-fit holdout scores on ag,ah,ai). Primary: AUC on the ag,ah,ai zones only. Based on the earlier pooled worker: Candidate B = same head recipe trained on pooled new-definition labels (group 5-fold out-of-fold); control = frozen candidate A scores (trained once on the 411 old-definition zones, stored from the two earlier holdout runs). Paired by photo group. Development only (these photos were already used once as holdouts)."""
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
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import view_tensors  # noqa: E402
DRAWS, SEED = 2000, 20261102
LAYER = 7  # 8th of 12 blocks, fixed before any score was seen


def layer_features(body, rows, device):
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
    if plan['hypothesis_id'] != 'surface-layer8-cv-20261102':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    b_scores = json.loads((ROOT/plan['last_layer_scores']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows'] or len(b_scores) != len(rows):
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = layer_features(body, rows, device)
    sw.fit = fit_pool
    scores = others.oof_scores(x, m, rows, cv.fold_of(rows))
    auc_b, auc_a = bag.auc(rows, scores), bag.auc(rows, b_scores)
    boot = paired_bootstrap(rows, scores, b_scores)
    crit = dict(diff=auc_b-auc_a >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, last_layer_scores=b_scores), allow_nan=False))
    by_src = {}
    for name, pick in (('older_yzaaa_adaeaf', lambda r: not any(f'20261102-{b}/' in r['image'] for b in ('ag', 'ah', 'ai'))), ('new_agahai', lambda r: any(f'20261102-{b}/' in r['image'] for b in ('ag', 'ah', 'ai')))):
        sel = [i for i, r in enumerate(rows) if pick(r)]
        sub = [rows[i] for i in sel]
        by_src[name] = dict(rows=len(sub), auc_b=bag.auc(sub, [scores[i] for i in sel]), auc_a=bag.auc(sub, [b_scores[i] for i in sel]))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_layer8=auc_b, auc_last_layer=auc_a, diff=auc_b-auc_a, diff_bootstrap=boot,
                   by_source=by_src, rows=len(rows), positive=sum(r['target'] for r in rows), groups=len({r['group'] for r in rows}), device=device,
                   typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
