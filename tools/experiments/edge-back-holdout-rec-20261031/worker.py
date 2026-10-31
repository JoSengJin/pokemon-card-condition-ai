"""Independent holdout, reference rows = holdout (intake p, 22 back photos, labels given before any score): control and pair-term heads fit once on pooled train+val (788 rows), scored on the holdout. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('gcv', ROOT/'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
pair, bag, sw = cv.pair, cv.bag, cv.sw


def by_area(rows, scores):
    out = {}
    for area in sorted({r['area'] for r in rows}):
        pos = [s for r, s in zip(rows, scores) if r['area'] == area and r['target']]
        neg = [s for r, s in zip(rows, scores) if r['area'] == area and not r['target']]
        out[area] = dict(positive=len(pos), normal=len(neg), auc=cv.roc(pos, neg) if pos and neg else None)
    return out


def summarize(rows, scores):
    return dict(auc=bag.auc(rows, scores), same_photo=bag.auc(rows, scores, True) if any(a['image'] == b['image'] and a['target'] != b['target'] for a in rows for b in rows) else None,
                fn=sum(r['target'] == 1 and s < .5 for r, s in zip(rows, scores)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(rows, scores)), by_area=by_area(rows, scores))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('edge-back-holdout-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    val = [r for r in rows if r['split'] == 'val']
    if [sum(r['split'] == 'train' for r in rows), len(val)] != plan['expected_denominators']['train_val'] or False:
        raise ValueError('Frozen denominator changed')
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows']:
        raise ValueError('Reference rows differ from the frozen holdout rows')
    if [sum(r['target'] for r in test), sum(1 - r['target'] for r in test), len({r['group'] for r in test})] != plan['expected_holdout']:
        raise ValueError('Frozen holdout denominator changed')
    separation = sw.check_separation(rows, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    xt, mt = sw.features(body, test, device)
    c_coef, c_bias, _ = sw.fit(x, m, rows)
    p_coef, p_bias, p_conv = pair.fit_pair(x, m, rows)
    control, paired = sw.score(xt, mt, c_coef, c_bias), sw.score(xt, mt, p_coef, p_bias)
    boot = cv.bootstrap(test, control, paired)
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=paired), allow_nan=False))
    c, p = summarize(test, control), summarize(test, paired)
    summary = dict(criterion_met=c['auc'] >= plan['criterion_min_auc'] and p['auc'] >= plan['criterion_min_auc'], control=c, pair=p, bootstrap=boot,
                   train_rows=len(rows), holdout_positive=sum(r['target'] for r in test), holdout_normal=sum(1 - r['target'] for r in test), holdout_groups=len({r['group'] for r in test}),
                   pair_converged=p_conv['converged'], separation=separation, device=device, typed_point_response='not_evaluated', training_calls=2, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
