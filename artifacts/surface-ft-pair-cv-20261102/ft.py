"""Fine-tune the last K DINOv2 blocks (+norm) with a patch-max linear head on cached block-(12-K) tokens of back-surface zone crops, with a same-photo defect/normal pair ranking loss. Views, masks and tokens are identical to the frozen recipe; only the training method differs. Common-runner only."""
import importlib.util
import copy
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('vl8', ROOT/'tools/experiments/surface-layer8-cv-r2-20261102/worker.py')
vl8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vl8)
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import view_tensors  # noqa: E402

CFG = dict(K=2, epochs=10, groups_per_batch=6, lr_blocks=1e-5, lr_head=1e-3, weight_decay=0.01, pair_weight=1.0, seed=20261102)  # fixed before any score was seen


def cache_tokens(body, rows, device):
    """Tokens entering block 12-K (cls + 1024 patches, fp16) and the physical-pixel patch mask per zone."""
    cache, done = {}, {}
    for r in rows:
        cache.setdefault(r['image'], []).append(r)
    stop = len(body.blocks) - CFG['K']
    with torch.inference_mode():
        for path, items in cache.items():
            for r, tensor in zip(items, view_tensors(path, [i['box'] for i in items], 448)):
                x = body.prepare_tokens_with_masks(tensor[None].to(device))
                for blk in body.blocks[:stop]:
                    x = blk(x)
                m = physical_pixel_mask(path, r['box'], halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
                done[r['id']] = (x.cpu()[0].half(), m)
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


class Tail(torch.nn.Module):
    """Last K blocks + norm copied from the frozen backbone, then a linear patch head with a masked max."""

    def __init__(self, body):
        super().__init__()
        self.blocks = torch.nn.ModuleList(copy.deepcopy(b) for b in body.blocks[-CFG['K']:])
        self.norm = copy.deepcopy(body.norm)
        self.head = torch.nn.Linear(self.norm.weight.shape[0], 1)
        torch.nn.init.zeros_(self.head.weight); torch.nn.init.zeros_(self.head.bias)

    def forward(self, x, mask):
        for blk in self.blocks:
            x = blk(x)
        logits = self.head(self.norm(x)[:, 1:]).squeeze(-1)
        return logits.masked_fill(~mask, -torch.inf).amax(1)


def loss_fn(logit, y, mass, gid):
    """Group-mass weighted BCE plus softplus pair ranking over defect/normal zones of the same photo."""
    bce = (F.binary_cross_entropy_with_logits(logit, y, reduction='none')*mass).sum()/mass.sum()
    same = (gid[:, None] == gid[None, :]) & (y[:, None] == 1) & (y[None, :] == 0)
    if not same.any():
        return bce
    diff = logit[:, None] - logit[None, :]
    return bce + CFG['pair_weight']*F.softplus(-diff[same]).mean()


def train_fold(body, X, M, rows, train_idx, device):
    torch.manual_seed(CFG['seed'])
    model = Tail(body).to(device).train()
    opt = torch.optim.AdamW([dict(params=list(model.blocks.parameters()) + list(model.norm.parameters()), lr=CFG['lr_blocks']), dict(params=model.head.parameters(), lr=CFG['lr_head'])], weight_decay=CFG['weight_decay'])
    count = {}
    for i in train_idx:
        count[rows[i]['group']] = count.get(rows[i]['group'], 0) + 1
    y_all = torch.tensor([rows[i]['target'] for i in train_idx], dtype=torch.float)
    mass_all = torch.tensor([1/count[rows[i]['group']] for i in train_idx])
    mass_all[y_all == 1] *= mass_all[y_all == 0].sum()/mass_all[y_all == 1].sum()
    by_group = {}
    for k, i in enumerate(train_idx):
        by_group.setdefault(rows[i]['group'], []).append(k)
    names = sorted(by_group)
    rng = torch.Generator().manual_seed(CFG['seed'])
    losses = []
    for _ in range(CFG['epochs']):
        order = torch.randperm(len(names), generator=rng).tolist()
        for s in range(0, len(order), CFG['groups_per_batch']):
            ks = [k for g in order[s:s + CFG['groups_per_batch']] for k in by_group[names[g]]]
            gid = torch.tensor([hash(rows[train_idx[k]]['group']) % 10**9 for k in ks], device=device)
            idx = torch.tensor([train_idx[k] for k in ks])
            logit = model(X[idx].float().to(device), M[idx].to(device))
            loss = loss_fn(logit, y_all[ks].to(device), mass_all[ks].to(device), gid)
            if not torch.isfinite(loss):
                raise ValueError('Non-finite loss')
            opt.zero_grad(); loss.backward(); opt.step(); losses.append(float(loss))
    return model.eval(), losses


def score(model, X, M, idx, device):
    out = []
    with torch.inference_mode():
        for s in range(0, len(idx), 64):
            sel = torch.tensor(idx[s:s + 64])
            out += model(X[sel].float().to(device), M[sel].to(device)).sigmoid().cpu().tolist()
    return out
