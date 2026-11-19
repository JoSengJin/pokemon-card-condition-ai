"""H3 (2026-11-20): does candidate F add value over a two-number image-quality rule? Same protocol as the whole-photo F measurement (fit once on the 267 dev rows, score the 219 eBay back rows, now development data by user decision 2026-11-20). Single changed variable: feature set (DINOv2 vits14 patch-mean 384-d -> 2 quality numbers: log Laplacian variance, highlight fraction > 245, both on the EXIF-rotated whole photo resized to long side 1024). Same standardized L2 logistic. Paired comparison against the frozen F scores of experiment 20261119T150351-39395830. Development only, not independent. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
HYPOTHESIS = 'obslimit-rule-h3-20261120'
LONG_SIDE = 1024


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h1 = _load('obsnobox', 'artifacts/obslimit-nobox-20261119/worker.py')
ms, bag, ps = h1.ms, h1.bag, h1.ps


def rule_features(path):
    with Image.open(path) as src:
        image = ImageOps.exif_transpose(src).convert('L')
    scale = LONG_SIDE/max(image.size)
    image = image.resize((max(1, round(image.width*scale)), max(1, round(image.height*scale))), Image.BILINEAR)
    gray = np.asarray(image, dtype=float)
    lap = gray[1:-1, 1:-1]*4-gray[:-2, 1:-1]-gray[2:, 1:-1]-gray[1:-1, :-2]-gray[1:-1, 2:]
    return [float(np.log1p(lap.var())), float((gray > 245).mean())]


def item_ids(rows):
    """eBay item_id per eBay-sourced group. Looks next to the photo first (alias groups keep source.json there), then under artifacts/*/<group>/."""
    items = {}
    for r in rows:
        if not r['group'].startswith('ebay'):
            continue
        source = Path(r['image']).parent/'source.json'
        if not source.exists():
            source = next((ROOT/'artifacts').glob(f"*/{r['group']}/source.json"), None)
        if source is None:
            raise ValueError('Missing source for ' + r['group'])
        items[r['group']] = json.loads(source.read_text())['item_id']
    return items


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
    if sum(r['target'] for r in rows) != plan['expected_positives']:
        raise ValueError('Eval denominators differ')
    return train, rows


def check_separation(train, rows, expected_train_ebay):
    if {r['group'] for r in train} & {r['group'] for r in rows} or {r['image_sha256'] for r in train} & {r['image_sha256'] for r in rows}:
        raise ValueError('Group or image overlap')
    tr, te = item_ids(train), item_ids(rows)
    if len(tr) != expected_train_ebay or set(tr.values()) & set(te.values()):
        raise ValueError('eBay item check incomplete or overlapping')


def verdict(delta, hi, crit):
    if delta >= crit['no_added_value_min_delta']:
        return 'f_no_added_value'
    if hi < 0:
        return 'f_adds_value'
    return 'inconclusive'


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    train, rows = check_inputs(plan, ref)
    check_separation(train, rows, plan['expected_train_ebay_groups'])
    f_scores = ref['before_scores']
    xtr = torch.tensor([rule_features(r['image']) for r in train], dtype=torch.float32)
    xte = torch.tensor([rule_features(r['image']) for r in rows], dtype=torch.float32)
    scores = ms.fit_predict(xtr, torch.tensor([r['target'] for r in train]), xte)
    auc_f, auc_r = bag.auc(rows, f_scores), bag.auc(rows, scores)
    delta = ps.paired(rows, f_scores, scores)
    result = verdict(auc_r-auc_f, delta['hi'], plan['criterion'])
    single = {name: bag.auc(rows, xte[:, k].tolist()) for k, name in enumerate(('log_laplacian_var', 'highlight_fraction'))}
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(verdict=result, criterion_met=result == 'f_no_added_value', rule=dict(auc=auc_r, bootstrap=ms.auc_ci(rows, scores), **h1.counts(rows, scores)),
                   f=dict(auc=auc_f, bootstrap=ms.auc_ci(rows, f_scores), **h1.counts(rows, f_scores)),
                   delta_auc=auc_r-auc_f, delta_bootstrap=delta, single_feature_auc_diagnostic=single,
                   train_ebay_groups_checked=plan['expected_train_ebay_groups'], rows=len(rows), train_rows=len(train),
                   training_calls=1, external_ai_calls=0, independent=False)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
