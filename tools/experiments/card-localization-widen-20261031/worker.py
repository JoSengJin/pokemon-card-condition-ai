"""Card-localization widen candidate: autobox.propose box widened 10% per side, then judged by corner containment and area ratio. Inference-free."""
import hashlib
import importlib.util
import json
import os
import statistics
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load('locbase', 'tools/experiments/card-localization-baseline-20261031/worker.py')
ab = base.ab
WIDEN = .10
MAX_AREA_RATIO = 2.0
BASELINE_EVAL = 'artifacts/experiments/20261030T223232-03b8fd5f/evaluation.json'


def widen(box, frac=WIDEN):
    """Grow each side outward by frac of the box width/height, clipped to the photo (0..1)."""
    dx, dy = (box[2] - box[0])*frac, (box[3] - box[1])*frac
    return [max(0.0, box[0] - dx), max(0.0, box[1] - dy), min(1.0, box[2] + dx), min(1.0, box[3] + dy)]


def passes(box, row):
    return base.contained(box, row['corners']) and base.area_ratio(box, row['box']) <= MAX_AREA_RATIO


def evaluate(rows):
    """Per face: raw autobox box must equal the baseline record (guard), then judge the widened box."""
    saved = {d['id']: d for d in json.loads((ROOT/BASELINE_EVAL).read_text())['detail']}
    detail = []
    for r in rows:
        raw, conf = ab.propose(r['image'])
        if raw != saved[r['id']]['box']:
            raise ValueError('autobox output differs from baseline record: ' + r['id'])
        box = widen(raw)
        detail.append(dict(id=r['id'], batch=r['batch'], raw_box=raw, box=box, conf=conf, contained=base.contained(box, r['corners']),
                           area_ratio=base.area_ratio(box, r['box']), passes=passes(box, r),
                           baseline_passes=passes(raw, r), baseline_contained=base.contained(raw, r['corners'])))
    return detail


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('card-localization-widen-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = base.faces()
    if json.loads(json.dumps(rows)) != ref['rows'] or len(rows) != plan['expected_denominators']['faces']:
        raise ValueError('Face set or reference rows changed')
    detail = evaluate(rows)
    if [1.0 if d['baseline_passes'] else 0.0 for d in detail] != ref['before_scores']:
        raise ValueError('Baseline conversion differs from reference')
    scores = [1.0 if d['passes'] else 0.0 for d in detail]
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores), allow_nan=False))
    failed = [d for d in detail if not d['passes']]
    summary = dict(faces=len(rows), unmet=len(failed), unmet_rate=len(failed)/len(rows), wilson95=base.wilson(len(failed), len(rows)),
                   baseline_unmet=sum(not d['baseline_passes'] for d in detail), criterion_max_unmet=plan['acceptance']['max_fn'],
                   criterion_met=len(failed) <= plan['acceptance']['max_fn'],
                   unmet_not_contained=sum(not d['contained'] for d in detail), unmet_area_over=sum(d['contained'] and d['area_ratio'] > MAX_AREA_RATIO for d in detail),
                   recovered=[d['id'] for d in detail if d['passes'] and not d['baseline_passes']], newly_unmet=[d['id'] for d in detail if not d['passes'] and d['baseline_passes']],
                   by_batch={b: dict(faces=sum(d['batch'] == Path(b).name for d in detail), unmet=sum(d['batch'] == Path(b).name and not d['passes'] for d in detail)) for b in base.BATCHES},
                   area_ratio_median=statistics.median(d['area_ratio'] for d in detail),
                   failed=failed, detail=detail, training_calls=0, external_ai_calls=0, model_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k not in ('detail', 'failed')}, ensure_ascii=False, default=float), flush=True)
