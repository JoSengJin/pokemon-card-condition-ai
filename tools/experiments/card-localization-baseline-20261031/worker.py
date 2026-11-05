"""Card-localization baseline: does autobox.propose (no training, no model) contain all 4 human corner points? Inference-free measurement."""
import hashlib
import importlib.util
import json
import math
import os
import statistics
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cr = _load('cr', 'artifacts/corner-rectify-20261030/worker.py')
ab = _load('ab', 'artifacts/ebay-intake-20261027-e/autobox.py')
from card_condition.ebay_dataset import decoded_hash  # noqa: E402

BATCHES = ('artifacts/ebay-intake-20261030-f', 'artifacts/ebay-intake-20261030-g')
EXCLUDED = 'ebay-pair-562d461bcf3f22'  # user-confirmed: card cut off by the photo edge
TOLERANCE = .005
ABSTAIN_BELOW = .7


def faces():
    """Back faces with 4 human corner points (TL, TR, BR, BL; normalized); photo bytes must match the intake list."""
    rows = []
    for batch in BATCHES:
        info = {f['id']: f for f in json.loads((ROOT/batch/'back-faces.json').read_text())}
        for key, corners in cr.load_corners((ROOT/batch/'corner-answers.txt').read_text()).items():
            if key == EXCLUDED:
                continue
            face = info[key]
            if decoded_hash(Path(face['image']).read_bytes())[0] != face['sha']:
                raise ValueError('Photo content changed: ' + key)
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            rows.append(dict(id=key, group=key, split='dev', target=1, image=face['image'], image_sha256=face['sha'],
                             box=[min(xs), min(ys), max(xs), max(ys)], corners=corners, batch=Path(batch).name))
    return rows


def contained(box, corners, tol=TOLERANCE):
    return all(box[0] - tol <= x <= box[2] + tol and box[1] - tol <= y <= box[3] + tol for x, y in corners)


def area_ratio(box, quad_box):
    return (box[2] - box[0])*(box[3] - box[1])/((quad_box[2] - quad_box[0])*(quad_box[3] - quad_box[1]))


def wilson(failures, total, z=1.96):
    p = failures/total
    centre = (p + z*z/(2*total))/(1 + z*z/total)
    half = z*math.sqrt(p*(1 - p)/total + z*z/(4*total*total))/(1 + z*z/total)
    return [round(centre - half, 3), round(centre + half, 3)]


def evaluate(rows):
    detail = []
    for r in rows:
        box, conf = ab.propose(r['image'])
        detail.append(dict(id=r['id'], batch=r['batch'], box=box, conf=conf, contained=contained(box, r['corners']),
                           area_ratio=area_ratio(box, r['box'])))
    return detail


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if not plan['hypothesis_id'].startswith('card-localization-baseline-'):
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = faces()
    if json.loads(json.dumps(rows)) != ref['rows'] or len(rows) != plan['expected_denominators']['faces']:
        raise ValueError('Face set or reference rows changed')
    detail = evaluate(rows)
    scores = [1.0 if d['contained'] else 0.0 for d in detail]
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores), allow_nan=False))
    failed = [d for d in detail if not d['contained']]
    flagged = [d for d in detail if d['conf'] < ABSTAIN_BELOW]
    provenance = {r['id']: contained(face['box'], r['corners']) for batch in BATCHES for face in json.loads((ROOT/batch/'back-faces.json').read_text())
                  for r in rows if r['id'] == face['id']}
    summary = dict(faces=len(rows), failures=len(failed), failure_rate=len(failed)/len(rows), wilson95=wilson(len(failed), len(rows)),
                   criterion_max_failures=plan['acceptance']['max_fn'], criterion_met=len(failed) <= plan['acceptance']['max_fn'],
                   by_batch={b: dict(faces=sum(d['batch'] == Path(b).name for d in detail), failures=sum(d['batch'] == Path(b).name and not d['contained'] for d in detail)) for b in BATCHES},
                   secondary_not_judged=dict(area_ratio_median=statistics.median(d['area_ratio'] for d in detail),
                                             share_area_ratio_le_2=sum(d['area_ratio'] <= 2 for d in detail)/len(detail),
                                             abstain_below=ABSTAIN_BELOW, flagged=len(flagged),
                                             failures_flagged=sum(d['conf'] < ABSTAIN_BELOW for d in failed),
                                             backfaces_json_boxes_contain=sum(provenance.values()), backfaces_json_note='proposer provenance unknown; reading only'),
                   failed=failed, detail=detail, training_calls=0, external_ai_calls=0, model_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k not in ('detail', 'failed')}, ensure_ascii=False, default=float), flush=True)
