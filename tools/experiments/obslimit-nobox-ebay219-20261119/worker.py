"""Measurement (2026-11-19): candidate F with the whole-photo input (H1 obslimit-nobox-20261119 passed on dev OOF) fitted once on all 267 dev rows, scored on the 219 new eBay back labels (restricted 59 / normal 160, adjudicated answers). No human box: every eval row uses the whole EXIF-rotated label photo. Train/eval separation is checked by group, eBay item_id and image SHA-256. Development measurement only, not independent. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
HYPOTHESIS = 'obslimit-nobox-ebay219-20261119'
WHOLE = [0., 0., 1., 1.]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h1 = _load('obsnobox', 'artifacts/obslimit-nobox-20261119/worker.py')
ms, bag = h1.ms, h1.bag


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


def check_separation(train, rows, train_items):
    if {r['group'] for r in train} & {r['group'] for r in rows}:
        raise ValueError('Group overlap')
    if {r['image_sha256'] for r in train} & {r['image_sha256'] for r in rows}:
        raise ValueError('Image overlap')
    for r in rows:
        if hashlib.sha256(Path(r['image']).read_bytes()).hexdigest() != r['image_sha256']:
            raise ValueError('Eval image changed: ' + r['id'])
    if train_items & {r['item_id'] for r in rows}:
        raise ValueError('eBay item overlap')


def train_item_ids(train):
    items = set()
    for r in train:
        if r['group'].startswith('ebay-pair-'):
            source = next((ROOT/'artifacts').glob(f"*/{r['group']}/source.json"), None)
            if source is None:
                raise ValueError('Missing source for ' + r['group'])
            items.add(json.loads(source.read_text())['item_id'])
    return items


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    train, rows = check_inputs(plan, ref)
    check_separation(train, rows, train_item_ids(train))
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xtr = h1.pooled(body, [dict(r, box=WHOLE) for r in train], device)
    xte = h1.pooled(body, rows, device)
    scores = ms.fit_predict(xtr, torch.tensor([r['target'] for r in train]), xte)
    auc, ci = bag.auc(rows, scores), ms.auc_ci(rows, scores)
    crit = plan['criterion']
    criterion = dict(auc=auc >= crit['min_auc'], auc_lower=ci['lo'] >= crit['min_auc_lower'],
                     rows=len(rows) >= crit['min_rows'], positives=sum(r['target'] for r in rows) >= crit['min_positives'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, auc=auc, bootstrap=ci, **h1.counts(rows, scores),
                   held=0, held_rate=0., excluded=plan['excluded_count'], rows=len(rows), train_rows=len(train), device=device,
                   training_calls=1, external_ai_calls=0, independent=False)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
