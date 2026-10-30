"""Card-localization stage 2: autobox raw vs 10% widened box on a seeded random sample of back faces. Primary = faces whose human 4 points are new (not used to design the candidate). Inference-free."""
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


wid = _load('locwid', 'tools/experiments/card-localization-widen-20261031/worker.py')
base, cr, ab = wid.base, wid.base.cr, wid.ab
from card_condition.ebay_dataset import decoded_hash  # noqa: E402

STAGE = 'artifacts/card-localization-stage2-20261031'
OLD = ('f', 'g')


def faces():
    """Sample faces with 4 human points (TL,TR,BR,BL); fresh=True when the points were collected for this stage. Photo bytes must match the intake list."""
    sample = json.loads((ROOT/STAGE/'sample.json').read_text())
    info = {f['id']: dict(f, batch=b) for b in 'fgh' for f in json.loads(next((ROOT/'artifacts').glob(f'ebay-intake-2026*-{b}/back-faces.json')).read_text())}
    corners = {}
    for batch in OLD:
        corners.update(cr.load_corners(next((ROOT/'artifacts').glob(f'ebay-intake-2026*-{batch}/corner-answers.txt')).read_text()))
    fresh = cr.load_corners((ROOT/STAGE/'corner-answers.txt').read_text())
    rows = []
    for key in sample['sample_ids']:
        if key == base.EXCLUDED:
            continue
        pts = fresh.get(key) or corners[key]
        face = info[key]
        if decoded_hash(Path(face['image']).read_bytes())[0] != face['sha']:
            raise ValueError('Photo content changed: ' + key)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rows.append(dict(id=key, group=key, split='dev', target=1, image=face['image'], image_sha256=face['sha'], box=[min(xs), min(ys), max(xs), max(ys)],
                         corners=pts, batch=face['batch'], fresh=key in fresh))
    return rows


def evaluate(rows):
    detail = []
    for r in rows:
        raw, conf = ab.propose(r['image'])
        box = wid.widen(raw)
        detail.append(dict(id=r['id'], batch=r['batch'], fresh=r['fresh'], raw_box=raw, box=box, conf=conf, area_ratio=base.area_ratio(box, r['box']),
                           raw_passes=wid.passes(raw, r), passes=wid.passes(box, r), contained=base.contained(box, r['corners'])))
    return detail


def arm(detail, key):
    unmet = sum(not d[key] for d in detail)
    return dict(faces=len(detail), unmet=unmet, unmet_rate=unmet/len(detail), wilson95=base.wilson(unmet, len(detail)))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('card-localization-stage2-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = faces()
    fresh_rows = [r for r in rows if r['fresh']]
    if json.loads(json.dumps(fresh_rows)) != ref['rows'] or len(fresh_rows) != plan['expected_denominators']['fresh']:
        raise ValueError('Fresh face set or reference rows changed')
    detail = evaluate(rows)
    fresh = [d for d in detail if d['fresh']]
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=[1.0 if d['passes'] else 0.0 for d in fresh]), allow_nan=False))
    summary = dict(primary_widen_fresh=arm(fresh, 'passes'), criterion_max_unmet=plan['acceptance']['max_fn'],
                   criterion_met=arm(fresh, 'passes')['unmet'] <= plan['acceptance']['max_fn'],
                   secondary_raw_fresh=arm(fresh, 'raw_passes'), secondary_widen_all=arm(detail, 'passes'), secondary_raw_all=arm(detail, 'raw_passes'),
                   secondary_widen_old=arm([d for d in detail if not d['fresh']], 'passes'),
                   by_batch_fresh={b: arm([d for d in fresh if d['batch'] == b], 'passes') for b in 'fgh' if any(d['batch'] == b for d in fresh)},
                   unmet_not_contained_fresh=sum(not d['contained'] for d in fresh), unmet_area_over_fresh=sum(d['contained'] and not d['passes'] for d in fresh),
                   area_ratio_median_fresh=statistics.median(d['area_ratio'] for d in fresh),
                   detail=detail, excluded=[base.EXCLUDED], training_calls=0, external_ai_calls=0, model_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'detail'}, ensure_ascii=False, default=float), flush=True)
