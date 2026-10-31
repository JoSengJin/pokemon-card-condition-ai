"""Fine-tune only the last DINOv2 block + norm + linear head (inputs to that block cached) with the same bag loss and within-photo pair term; 20 group-bootstrap fits + 1 full fit; scored once on frozen val. Common-runner only."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('l8w', ROOT/'tools/experiments/edge-back-layer8-pair-20261031/worker.py')
l8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l8)
vs, pair, bag, sw = l8.vs, l8.pair, l8.bag, l8.sw
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import view_tensors  # noqa: E402
from confounder_head import detail_bag_loss  # noqa: E402

EPOCHS, BATCH_ROWS, LR_BLOCK, LR_HEAD, DECAY, CLIP = 15, 24, 5e-5, 1e-3, 1e-2, 1.0  # fixed before any score was seen


def cache_inputs(body, rows, device):
    """Tokens entering the last block (1025x384, half precision) and the physical patch masks, per row."""
    cache, done = {}, {}
    for r in rows:
        cache.setdefault(r['image'], []).append(r)
    with torch.inference_mode():
        for path, items in cache.items():
            for r, tensor in zip(items, view_tensors(path, [i['box'] for i in items], 448)):
                x = body.prepare_tokens_with_masks(tensor[None].to(device))
                for blk in body.blocks[:-1]:
                    x = blk(x)
                m = physical_pixel_mask(path, r['box'], halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
                done[r['id']] = (x.cpu()[0].half(), m)
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


class LastBlock(torch.nn.Module):
    def __init__(self, body):
        super().__init__()
        self.block, self.norm, self.head = copy.deepcopy(body.blocks[-1]), copy.deepcopy(body.norm), torch.nn.Linear(384, 1)
        torch.nn.init.zeros_(self.head.weight)
        torch.nn.init.zeros_(self.head.bias)

    def forward(self, x):
        return self.head(self.norm(self.block(x))[:, 1:]).squeeze(-1)


def train_once(body, xin, masks, rows, seed, device):
    """Photo-grouped mini-batches so pair terms stay inside a batch; mass-weighted max_bound bag loss + smooth pair term; fixed epochs, no validation use."""
    torch.manual_seed(seed)
    model = LastBlock(body).to(device).train()
    y, mass = pair.masses(rows)
    photos = {}
    for i, r in enumerate(rows):
        photos.setdefault(r['image'], []).append(i)
    keys = sorted(photos)
    opt = torch.optim.AdamW([dict(params=list(model.block.parameters()) + list(model.norm.parameters()), lr=LR_BLOCK),
                             dict(params=model.head.parameters(), lr=LR_HEAD)], weight_decay=DECAY)
    for _ in range(EPOCHS):
        order, batches, current = torch.randperm(len(keys)).tolist(), [], []
        for k in order:
            current += photos[keys[k]]
            if len(current) >= BATCH_ROWS:
                batches.append(current)
                current = []
        batches += [current] if current else []
        for idx in batches:
            logits = model(xin[idx].float().to(device))
            valid = masks[idx].to(device)
            m = mass[idx].float().to(device)
            base = sum(m[j]*detail_bag_loss(logits[j], int(y[i]), valid[j], None, 'max_bound') for j, i in enumerate(idx))/m.sum()
            s = pair.TAU*torch.logsumexp(logits.masked_fill(~valid, -torch.inf)/pair.TAU, 1)
            groups = {}
            for j, i in enumerate(idx):
                groups.setdefault(rows[i]['image'], ([], []))[0 if y[i] else 1].append(j)
            terms = [F.softplus(-(s[torch.tensor(p)][:, None] - s[torch.tensor(n)][None, :])).mean() for p, n in groups.values() if p and n]
            loss = base + (pair.LAMBDA*torch.stack(terms).mean() if terms else 0)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
            opt.step()
    return model.eval()


def score_val(model, xin, masks, device):
    out = []
    with torch.inference_mode():
        for i in range(0, len(xin), 32):
            logits = model(xin[i:i + 32].float().to(device)).cpu()
            out += logits.masked_fill(~masks[i:i + 32], -torch.inf).amax(1).sigmoid().tolist()
    return out


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-lastblock-ft-'):
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
    xt, mt = cache_inputs(body, train, device)
    xv, mv = cache_inputs(body, val, device)
    pair_rows = [dict(r, image=f"{r['image']}#{r['group']}") for r in train]
    full = score_val(train_once(body, xt, mt, pair_rows, bag.SEED, device), xv, mv, device)
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=full), allow_nan=False))
    heads, redraws, seed = [], 0, bag.SEED
    while len(heads) < bag.BAGS:
        index, brows = bag.resample(train, seed)
        seed += 1
        brows = [dict(r, image=f"{r['image']}#{r['group']}") for r in brows]
        if len({r['target'] for r in brows}) < 2 or not pair.photo_pairs(brows):
            redraws += 1
            continue
        heads.append(score_val(train_once(body, xt[index], mt[index], brows, seed, device), xv, mv, device))
    spread = vs.spread(val, heads)
    ens = torch.tensor(heads).mean(0).tolist()
    summary = dict(finetuned_bootstrap=spread, criterion_min_mean_auc=plan['criterion_min_mean_auc'], criterion_met=spread['mean'] >= plan['criterion_min_mean_auc'],
                   frozen_pair_bootstrap_mean=.7013875365141188, frozen_pair_bootstrap_std=.04740107906933811,
                   full=dict(auc=bag.auc(val, full), same_photo=bag.auc(val, full, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, full)),
                             fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, full))),
                   ensemble=dict(auc=bag.auc(val, ens), same_photo=bag.auc(val, ens, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(val, ens)),
                                 fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(val, ens))),
                   head3_auc=bag.auc(val, ref['before_scores']), val_positive=sum(r['target'] for r in val), val_normal=sum(1 - r['target'] for r in val),
                   hyper=dict(epochs=EPOCHS, batch_rows=BATCH_ROWS, lr_block=LR_BLOCK, lr_head=LR_HEAD, weight_decay=DECAY, clip=CLIP), redraws=redraws,
                   train_units=len(train), device=device, separation=separation, typed_point_response='not_evaluated', training_calls=1 + bag.BAGS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
