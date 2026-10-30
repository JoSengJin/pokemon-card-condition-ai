"""Back-edge area presence head fitted on train units only; scored once on frozen val. Common-runner only."""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'artifacts/inner-whitening-confounder-20261021'))
import torch  # noqa: E402
from card_condition.regions import region_box  # noqa: E402
from card_condition.ebay_dataset import decoded_hash  # noqa: E402
from card_condition.local_wear_cnn import physical_pixel_mask  # noqa: E402
from card_condition.side_experiment import view_tensors  # noqa: E402
from confounder_head import fit_detail_head  # noqa: E402


def edge_rows(coverage):
    """Reviewed back edge units with explicit human truth; unreviewed boxes are never guessed."""
    rows = []
    for u in coverage['units']:
        if u['label'] != 'edge_defect' or u['side'] != 'back' or u['target'] is None or u['box_reviewed'] is not True:
            continue
        rows.append(dict(id=f"{u['card_id']}/back/edge/{u['area']}", group=u['group'], split=u['split'],
                         image=u['image'], image_sha256=u['image_sha256'], area=u['area'], target=u['target'],
                         box=region_box(u['card_box'], u['area'])))
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate edge unit identity')
    return rows


def check_separation(train, val):
    ids = {}
    for r in train + val:
        data = Path(r['image']).read_bytes()
        raw = hashlib.sha256(data).hexdigest()
        ids[r['image']] = {raw, decoded_hash(data)[0]}
        if r['image_sha256'] not in ids[r['image']]:
            raise ValueError('Photo content changed: ' + r['id'])
    groups = {r['group'] for r in train} & {r['group'] for r in val}
    photos = {s for r in train for s in ids[r['image']]} & {s for r in val for s in ids[r['image']]}
    if groups or photos:
        raise ValueError('Train and val overlap')
    return dict(group_overlap=0, photo_overlap=0)


def features(body, rows, device):
    values, masks, cache = [], [], {}
    for r in rows:
        cache.setdefault(r['image'], []).append(r)
    done = {}
    with torch.inference_mode():
        for path, items in cache.items():
            for r, tensor in zip(items, view_tensors(path, [i['box'] for i in items], 448)):
                z = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
                if z.shape != (1024, 384) or not torch.isfinite(z).all():
                    raise ValueError('Unexpected feature tensor')
                m = physical_pixel_mask(path, r['box'], halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
                done[r['id']] = (z, m)
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


def fit(x, masks, rows):
    y = torch.tensor([r['target'] for r in rows])
    count = Counter(r['group'] for r in rows)
    mass = torch.tensor([1/count[r['group']] for r in rows])
    mass[y == 1] *= mass[y == 0].sum()/mass[y == 1].sum()
    return fit_detail_head(x, masks, y, torch.full((len(rows),), -1, dtype=torch.long), mass, penalty=1., normal_reduction='max_bound')


def score(x, masks, coef, bias):
    logits = x @ coef + bias
    return logits.masked_fill(~masks, -torch.inf).amax(1).sigmoid().tolist()


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-area-presence-head-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    coverage = json.loads((ROOT/plan['coverage']).read_text())
    rows = edge_rows(coverage)
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'val']
    if [len(train), len(val)] != plan['expected_denominators']['train_val'] or [dict(r, **{}) for r in val] != ref['rows']:
        raise ValueError('Frozen denominator or reference rows changed')
    separation = check_separation(train, val)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = features(body, train, device)
    xv, mv = features(body, val, device)
    coef, bias, convergence = fit(xt, mt, train)
    scores = score(xv, mv, coef, bias)
    train_scores = score(xt, mt, coef, bias)
    torch.save(dict(coef=coef, bias=bias, train_ids=[r['id'] for r in train]), out/'head.pt')
    torch.save(dict(rows=val, features=xv, masks=mv, scores=scores), out/'val-features.pt')
    (out/'observations.json').write_text(json.dumps(dict(rows=val, scores=scores), allow_nan=False))
    fn = sum(r['target'] == 1 and s < .5 for r, s in zip(val, scores))
    fp = sum(r['target'] == 0 and s >= .5 for r, s in zip(val, scores))
    summary = dict(device=device, train_units=len(train), val_units=len(val), separation=separation, convergence=convergence,
                   val_fn=fn, val_positive=sum(r['target'] for r in val), val_fp=fp, val_normal=sum(1-r['target'] for r in val),
                   train_fit_fn=sum(r['target'] == 1 and s < .5 for r, s in zip(train, train_scores)),
                   train_fit_fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(train, train_scores)),
                   typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
