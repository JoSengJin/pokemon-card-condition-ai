"""Does adding 168 newly labeled back-corner zones (48 photos, 10 groups partly overlapping) improve the pooled group 5-fold CV of the back-corner control head? Same recipe as triage-others (ViT-S/14 448 tokens + control head); only the training/CV rows grow. Primary comparison uses the ORIGINAL 170 zones as a same-denominator subset of the new out-of-fold scores. Development evaluation, not independent. Common-runner only."""
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


others = _load('others', 'tools/experiments/edge-back-triage-others-20261101/worker.py')
cv, tr, bag, sw = others.cv, others.tr, others.bag, others.sw


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'edge-back-corner-more-cv-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    scores = others.oof_scores(x, m, rows, cv.fold_of(rows))
    old_ids = {r['id'] for r in json.loads((ROOT/plan['old_rows']).read_text()) if r['category'] == 'corner_defect:back'}
    sel = [i for i, r in enumerate(rows) if r['id'] in old_ids]
    orows, oscores = [rows[i] for i in sel], [scores[i] for i in sel]
    low, high = plan['band_low'], plan['band_high']
    res = dict(
        all=dict(rows=len(rows), positive=sum(r['target'] for r in rows), groups=len({r['group'] for r in rows}), auc=bag.auc(rows, scores),
                 metrics=tr.metrics(rows, scores, low, high), bootstrap=tr.bootstrap(rows, scores, low, high)),
        original=dict(rows=len(orows), positive=sum(r['target'] for r in orows), groups=len({r['group'] for r in orows}), auc=bag.auc(orows, oscores),
                      metrics=tr.metrics(orows, oscores, low, high)),
        new_only=dict(rows=len(rows) - len(orows), auc=bag.auc([r for i, r in enumerate(rows) if i not in set(sel)], [s for i, s in enumerate(scores) if i not in set(sel)])))
    crit = dict(original_auc=res['original']['auc'] >= plan['criterion_original_auc'], all_auc=res['all']['auc'] >= plan['criterion_all_auc'],
                all_gap=res['all']['metrics']['gap'] is not None and res['all']['metrics']['gap'] >= plan['criterion_all_gap'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, result=res, band_low=low, band_high=high, device=device, typed_point_response='not_evaluated',
                   training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
