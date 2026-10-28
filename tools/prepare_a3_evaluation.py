"""Prepare pinned development-val inputs and truth-free requests; no model calls."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.data import load_manifest
from card_condition.data_coverage import coverage_report
from card_condition.evaluation_inputs import track_photos, unchanged_inputs
from card_condition.evaluation_output import write_new_report
from card_condition.listing_coverage import truth_cells
from card_condition.listing_model import photo_request
from card_condition.point_dataset import point_rows
from freeze_dev_manifest import audit


def request_for(row):
    request = dict(id=row['id'])
    for side in ('front', 'back'):
        if not row.get(side):
            continue
        annotation = row.get('side_annotations', {}).get(side, {})
        face = dict(image=row[side])
        if annotation.get('box_reviewed') is True:
            face['box'] = copy.deepcopy(annotation['box'])
        if 'visibility_issues' in annotation:
            face['visibility_issues'] = list(annotation['visibility_issues'])
            # Local glare geometry is meaningful only with a confirmed card box.
            if face.get('box') is not None and 'glare_areas' in annotation:
                face['glare_areas'] = list(annotation['glare_areas'])
        request[side] = face
    photo_request(request)
    return request


def prepare(manifest, manifest_sha256, coverage, coverage_sha256, output):
    output, manifest, coverage = Path(output), Path(manifest).resolve(), Path(coverage).resolve()
    if output.exists():
        raise ValueError('Output exists: choose a new preparation directory')
    hashes = {str(manifest): manifest_sha256, str(coverage): coverage_sha256}
    unchanged_inputs(hashes)
    frozen = json.loads(coverage.read_bytes())
    actual = coverage_report(manifest)
    if actual != frozen:
        raise ValueError('Coverage differs from the pinned source projection')
    records = load_manifest(manifest, splits={'train', 'val'}, require_gradable=False)
    errors, warnings = audit(records)
    if any(e['split'] == 'val' for e in errors):
        raise ValueError('Validation coordinate audit has errors')
    selected = [r for r in records if r['split'] == 'val']
    active = [r for r in selected if not r.get('excluded')]
    if not active:
        raise ValueError('No active validation records')
    track_photos(records, hashes)
    patches, projection = point_rows(manifest, grid=True, splits={'val'})
    expected_photos = {r['id']: dict(zip((s for s in ('front', 'back') if r.get(s)), r['_image_hashes'])) for r in active}
    if projection['manifest_sha256'] != manifest_sha256 or projection['input_image_hashes'] != expected_photos:
        raise ValueError('Source changed between preparation passes')
    cells = truth_cells(active, patches)
    requests = [request_for(r) for r in active]
    exported = [{k: v for k, v in r.items() if k != '_image_hashes'} for r in selected]
    content = ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in exported)
    denominators = dict(
        c_cells=[c for c in frozen['cells'] if c['split'] == 'val'],
        c_units=[u for u in frozen['units'] if u['split'] == 'val'],
        c_typed_points=[p for p in frozen['typed_points'] if p['split'] == 'val'],
        e2_cells=cells,
        e2_known_observable=sum(c['excluded_reason'] is None for c in cells),
        e2_exclusions=dict(Counter(c['excluded_reason'] for c in cells if c['excluded_reason'])))
    unchanged_inputs(hashes)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'requests').mkdir()
    with (output / 'val.jsonl').open('x', encoding='utf-8') as stream:
        stream.write(content)
    write_new_report(output / 'denominators.json', denominators)
    request_index = []
    for number, request in enumerate(requests):
        name = f'requests/{number:04d}.json'
        write_new_report(output / name, request)
        request_index.append(dict(id=request['id'], path=name,
                                  sha256=hashlib.sha256((output / name).read_bytes()).hexdigest()))
    files = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
             for name in ('val.jsonl', 'denominators.json')}
    unchanged_inputs(hashes)
    report = dict(schema='a3_evaluation_preparation/v1', source_manifest_sha256=manifest_sha256,
        source_coverage_sha256=coverage_sha256, split='val', rows=len(selected),
        active_rows=len(active), excluded_rows=len(selected)-len(active),
        physical_cards=len({r['group'] for r in active}), files=files, requests=request_index,
        input_hashes=hashes, c_quantity_cells_met=sum(c['quantity_met'] for c in denominators['c_cells']),
        c_cells=len(denominators['c_cells']), e2_known_observable=denominators['e2_known_observable'],
        e2_required_cells=len(cells), e2_exclusions=denominators['e2_exclusions'],
        audit_errors=errors, audit_warnings=warnings, predictions=None, nondeferred_coverage=None,
        training_calls=0, inference_calls=0, independent=False, d1_use=False, e2_verified=False,
        production_ready=False, labels_modified=False,
        next_required=['Pin one executable candidate and verify its training group/photo separation.',
                       'Run scored evaluation through the common experiment recorder; do not relabel val as test.'],
        limitations=['C counts all known frozen units; E2 additionally requires human-observable reviewed geometry.',
                     'Prepared requests contain no defect labels or points; missing observation review remains missing.',
                     'Preparation is not a prediction, measured coverage, model-quality pass or independent trial.',
                     'report.json is the completion marker; a failed preparation may leave a new partial directory.'])
    write_new_report(output / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--coverage', required=True)
    parser.add_argument('--coverage-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.manifest, args.manifest_sha256, args.coverage, args.coverage_sha256, args.output)
    print(json.dumps({k: result[k] for k in ('rows', 'active_rows', 'c_quantity_cells_met', 'e2_known_observable', 'inference_calls')}, ensure_ascii=False))
