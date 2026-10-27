"""Read-only E2 coverage from frozen human truth and saved listing-predict outputs."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import torch

from .data import load_manifest
from .evaluation_inputs import track_photos, unchanged_inputs, reject_copied_test_groups
from .evaluation_output import write_new_report
from .listing_coverage_inputs import pinned_json, bundle_cases, checked_case
from .point_dataset import point_rows
from .regions import REGION_TARGET_AREAS
from .release import read_release


def truth_cells(records, patches):
    projected = {(r['card_id'], r['side'], r['area']): r['labels'] for r in patches}
    result, seen_photos = [], set()
    for row in records:
        for digest in row['_image_hashes']:
            if digest in seen_photos:
                raise ValueError('Duplicate decoded photo in coverage population')
            seen_photos.add(digest)
        for side in ('front', 'back'):
            face = row.get('side_annotations', {}).get(side, {})
            issues, glare = face.get('visibility_issues'), face.get('glare_areas', [])
            keys = [(label, area) for label, areas in REGION_TARGET_AREAS.items() for area in areas]
            keys += [('centering_defect', 'face'), ('observation_limited', 'face')]
            for label, area in keys:
                truth = (int(bool(issues)) if issues is not None else None) if label == 'observation_limited' else (
                    face.get('labels', {}).get(label) if area == 'face' else
                    projected.get((row['id'], side, area), {}).get(label))
                limited = bool(issues) if area == 'face' else (bool(set(issues or []) - {'glare'})
                    or 'glare' in (issues or []) and (not glare or area in glare))
                reason = ('missing_source_photo' if not row.get(side) else
                          'unreviewed_geometry' if face.get('box_reviewed') is not True else
                          'observation_not_reviewed' if issues is None else
                          'human_observation_limited' if limited else
                          'unknown_truth' if truth is None else None)
                result.append(dict(card_id=row['id'], group=row['group'], side=side, area=area, label=label,
                                   truth=truth, excluded_reason=reason))
    return result


def assess_coverage(manifest, release_path, bundle_path, bundle_sha256, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new coverage report path')
    hashes = {}
    bundle_path = Path(bundle_path).resolve()
    bundle = pinned_json(bundle_path, bundle_sha256, hashes)
    for path, key in ((manifest, 'manifest_sha256'), (release_path, 'release_sha256')):
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != bundle.get(key):
            raise ValueError('Frozen manifest or release SHA256 mismatch')
        hashes[str(Path(path).resolve())] = bundle[key]
    release, files = read_release(release_path)
    if release['manifest_sha256'] != bundle['release_sha256']:
        raise ValueError('Release changed while loading')
    for role, path in files.items():
        hashes[str(Path(path).resolve())] = release['checkpoint_sha256'][role]
    checkpoint_raw = Path(files['region']).read_bytes()
    if hashlib.sha256(checkpoint_raw).hexdigest() != release['checkpoint_sha256']['region']:
        raise ValueError('Region checkpoint changed while loading')
    meta = torch.load(io.BytesIO(checkpoint_raw), map_location='cpu', weights_only=True)
    supported = meta.get('supported') if isinstance(meta, dict) else None
    if (not isinstance(supported, list) or not supported or any(type(q) is not str or q not in REGION_TARGET_AREAS for q in supported)
            or len(set(supported)) != len(supported)):
        raise ValueError('Invalid region checkpoint supported scope')
    records = [r for r in load_manifest(manifest, require_gradable=False) if not r.get('excluded')]
    splits = {r['split'] for r in records}
    if splits not in ({'val'}, {'test'}):
        raise ValueError('Coverage requires one explicit val or test population; no train or mixed splits')
    reject_copied_test_groups(records)
    track_photos(records, hashes)
    patches, _ = point_rows(manifest, grid=True, splits=splits)
    truths = truth_cells(records, patches)
    cases, states = bundle_cases(bundle, records), {}
    metadata = {r['id']: r for r in records}
    for ident, case in cases.items():
        request = pinned_json(bundle_path.parent / case['request']['path'], case['request']['sha256'], hashes)
        report = pinned_json(bundle_path.parent / case['report']['path'], case['report']['sha256'], hashes)
        if report.get('architecture') != meta.get('architecture') or report.get('image_size') != meta.get('image_size', 224):
            raise ValueError('Saved listing architecture or image size mismatch')
        states[ident] = checked_case(metadata[ident], request, report, release, supported, hashes)
    exclusions, holds, cells = {}, {}, []
    for cell in truths:
        state = states.get(cell['card_id'], {}).get((cell['side'], cell['area'], cell['label']))
        reason, held = cell['excluded_reason'], None
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
        else:
            held = ('missing_report' if cell['card_id'] not in states else
                    'centering_not_evaluated' if cell['label'] == 'centering_defect' else
                    'whole_listing_observability_not_validated' if cell['label'] == 'observation_limited' else state['reason'])
            if held:
                holds[held] = holds.get(held, 0) + 1
        cells.append(dict(cell, model_state=state['state'] if state else 'unknown',
                          model_reason=reason or held, included=reason is None))
    denominator = sum(c['included'] for c in cells)
    numerator = sum(c['included'] and c['model_state'] in ('normal', 'defect') for c in cells)
    coverage = numerator / denominator if denominator else None
    by_question_side = []
    for question in (*REGION_TARGET_AREAS, 'centering_defect', 'observation_limited'):
        for side in ('front', 'back'):
            part = [c for c in cells if c['label'] == question and c['side'] == side and c['included']]
            accepted = sum(c['model_state'] in ('normal', 'defect') for c in part)
            by_question_side.append(dict(question=question, side=side, known_observable_cells=len(part),
                                         nondeferred_cells=accepted, coverage=accepted/len(part) if part else None))
    unchanged_inputs(hashes)
    result = dict(schema_version=1, evaluation_kind='saved_listing_coverage', release=release,
        manifest_sha256=bundle['manifest_sha256'], input_hashes=hashes, split=next(iter(splits)),
        listings=len(records), physical_cards=len({r['group'] for r in records}), supplied_reports=len(states),
        missing_reports=sorted(set(metadata) - set(states)), required_cells=len(cells),
        known_observable_cells=denominator, nondeferred_cells=numerator, deferred_cells=denominator-numerator,
        coverage=coverage, numeric_condition_met=coverage is not None and coverage >= .7,
        excluded_cells=exclusions, hold_reasons=holds, by_question_side=by_question_side, cells=cells,
        training_performed=False, inference_performed=False, e2_verified=False, production_ready=False,
        limitations=['Coverage is not correctness; C raw FN/FP denominators and thresholds are unchanged.',
            'Unknown labels and unreviewed/limited source regions are disclosed, never inferred as normal.',
            'Whole-face model verdicts remain held because the current listing API does not provide them.',
            'Missing requests/results and unsupported known cells stay in the frozen denominator.',
            'Saved scores are recomputed into states; score-generation correctness needs separate audit.',
            'This does not establish independent-test provenance or completion of human review scenarios.'])
    write_new_report(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'release', 'bundle', 'output'):
        parser.add_argument(name)
    parser.add_argument('--bundle-sha256', required=True)
    args = parser.parse_args()
    try:
        report = assess_coverage(args.manifest, args.release, args.bundle, args.bundle_sha256, args.output)
        print(json.dumps({k: v for k, v in report.items() if k not in ('cells', 'input_hashes')}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'Coverage inputs or output path failed validation; no report accepted.\n')
