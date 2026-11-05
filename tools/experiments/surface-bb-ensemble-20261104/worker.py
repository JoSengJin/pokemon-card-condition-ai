"""Score-level ensemble: mean of the ViT-S/14 and ViT-B/14 out-of-fold scores of the same 1791 pooled zones (no new training); control = ViT-S/14 scores. Development only. Reuses paired_bootstrap and auc helpers from the negfilter worker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load('base', 'tools/experiments/surface-negfilter-cv-20261104/worker.py')
bag = base.bag

if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-bb-ensemble-20261104':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    b = json.loads((ROOT/plan['vitb14_observations']).read_text())
    s_scores = json.loads((ROOT/plan['vits14_scores']).read_text())
    if rows != ref['rows'] or rows != b['rows'] or b['vits14_scores'] != s_scores or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    scores = [(x+y)/2 for x, y in zip(s_scores, b['scores'])]
    auc_e, auc_s, auc_b = bag.auc(rows, scores), bag.auc(rows, s_scores), bag.auc(rows, b['scores'])
    boot = base.paired_bootstrap(rows, scores, s_scores)
    crit = dict(diff=auc_e-auc_s >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, vits14_scores=s_scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_ensemble=auc_e, auc_vits14=auc_s, auc_vitb14=auc_b, diff=auc_e-auc_s,
                   diff_bootstrap=boot, rows=len(rows), positive=sum(r['target'] for r in rows), groups=len({r['group'] for r in rows}),
                   typed_point_response='not_evaluated', training_calls=0, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
