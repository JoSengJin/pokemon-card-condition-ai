"""Bind saved evaluations to one pinned candidate, input seal and exposure receipts."""
import json
import math
from pathlib import Path

from .frozen_candidate import OPERATIONS, read_candidate
from .frozen_test import read_seal
from .release import file_sha256

KINDS = dict(region_final=('region_final', 'point_final'), side_final=('final',),
             observation_final=('heldout_observation_test',))


def matched_reports(candidate_path, candidate_sha256, seal_path, seal_sha256, manifest, reports):
    if (not isinstance(reports, dict) or not reports or set(reports) - set(OPERATIONS)
            or file_sha256(candidate_path) != candidate_sha256):
        raise ValueError('Explicit role reports and the pinned candidate SHA256 are required')
    candidate = json.loads(Path(candidate_path).read_text())
    if not isinstance(candidate, dict) or not isinstance(candidate.get('models'), dict):
        raise ValueError('Invalid candidate')
    seal, hashes = read_seal(seal_path, seal_sha256, manifest)
    sealed_hashes = dict(hashes)
    found = {}
    for op, supplied in reports.items():
        if (not isinstance(supplied, dict) or set(supplied) != {'path', 'sha256'}
                or type(supplied['path']) is not str or type(supplied['sha256']) is not str):
            raise ValueError('Each saved report requires its original path and SHA256')
        report_path = supplied['path']
        if op not in candidate['models'] or not isinstance(candidate['models'][op], dict) or 'file' not in candidate['models'][op]:
            raise ValueError('Report role was not planned in this candidate')
        checked, pinned = read_candidate(candidate_path, candidate_sha256, seal_sha256,
                                         candidate['models'][op]['file'], op, candidate.get('device'))
        hashes.update(pinned)
        report_path = Path(report_path).resolve()
        before = file_sha256(report_path)
        if before != supplied['sha256']:
            raise ValueError('Saved evaluation report SHA256 mismatch')
        report = json.loads(report_path.read_text())
        if not isinstance(report, dict):
            raise ValueError('Evaluation report must be an object')
        link = report.get('test_seal')
        if not isinstance(report.get('input_hashes'), dict):
            raise ValueError('Evaluation must record frozen input hashes')
        recorded_manifest_sha = report.get('manifest_sha256', report['input_hashes'].get(str(Path(manifest).resolve())))
        if (report.get('evaluation_kind') not in KINDS[op] or recorded_manifest_sha != seal['manifest_sha256']
                or report.get('model_sha256') != checked['models'][op]['sha256']
                or report.get('threshold', .5) != .5
                or report.get('physical_card_uncertainty', {}).get('threshold') != .5
                or not isinstance(report.get('input_hashes'), dict) or not isinstance(link, dict)
                or link.get('seal_sha256') != seal_sha256 or link.get('candidate_sha256') != candidate_sha256
                or link.get('operation') != op or link.get('status') != 'exposure_claimed'
                or type(link.get('receipt')) is not str or type(link.get('receipt_sha256')) is not str):
            raise ValueError('Evaluation identity does not match the frozen candidate and seal')
        if any(report['input_hashes'].get(name) != sha for name, sha in {**sealed_hashes, **pinned}.items()):
            raise ValueError('Evaluation did not record every pinned input')
        receipt_path = Path(link['receipt']).resolve()
        if file_sha256(receipt_path) != link['receipt_sha256']:
            raise ValueError('Exposure receipt SHA256 mismatch')
        receipt = json.loads(receipt_path.read_text())
        if (not isinstance(receipt, dict) or receipt.get('kind') != 'frozen_test_use'
                or receipt.get('status') != 'exposure_claimed' or receipt.get('operation') != op
                or receipt.get('candidate_sha256') != candidate_sha256 or receipt.get('seal_sha256') != seal_sha256
                or receipt.get('model_sha256') != checked['models'][op]['sha256']
                or receipt.get('manifest_sha256') != seal['manifest_sha256']
                or receipt.get('physical_groups') != seal['physical_groups']
                or receipt.get('decoded_photo_sha256') != seal['decoded_photo_sha256']):
            raise ValueError('Exposure receipt identity mismatch')
        # Extra recorded inputs are also frozen; they cannot silently drift after the original evaluation.
        for name, sha in report['input_hashes'].items():
            if file_sha256(name) != sha:
                raise ValueError('An evaluation input changed after the run')
            hashes[name] = sha
        hashes[str(report_path)] = before
        hashes[str(receipt_path)] = link['receipt_sha256']
        found[op] = report
    return candidate, seal, found, hashes


def checked_predictions(report, rows, operation, supported):
    """Match the original projection exactly; side reports carry only id/labels/probabilities."""
    expected = {}
    for row in rows:
        key = (row['card_id'], row['side']) if operation == 'observation_final' else row['id']
        if key in expected:
            raise ValueError('Duplicate source judgment unit')
        expected[key] = row
    predictions = report.get('predictions')
    if not isinstance(predictions, list):
        raise ValueError('Missing evaluation predictions')
    normalized, seen = [], set()
    for item in predictions:
        if not isinstance(item, dict):
            raise ValueError('Invalid prediction')
        key = (item.get('card_id'), item.get('side')) if operation == 'observation_final' else item.get('id')
        if (operation == 'observation_final' and not all(type(k) is str for k in key)
                or operation != 'observation_final' and type(key) is not str or key not in expected or key in seen):
            raise ValueError('Prediction is additional, duplicate or unmatched')
        row = expected[key]
        fields = ('id', 'labels') if operation == 'side_final' else tuple(row)
        if any(json.dumps(item.get(field), sort_keys=True, allow_nan=False) !=
               json.dumps(row[field], sort_keys=True, allow_nan=False) for field in fields):
            raise ValueError('Prediction truth, identity or geometry differs from the sealed source')
        probs = item.get('probabilities')
        if (not isinstance(probs, dict) or set(probs) != set(row['labels'])
                or any(v is not None and (type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1)
                       for v in probs.values())
                or any(v is not None and label not in supported for label, v in probs.items())):
            raise ValueError('Invalid or unsupported raw prediction score')
        normalized.append(dict(row, probabilities=probs))
        seen.add(key)
    if seen != set(expected):
        raise ValueError('Evaluation omitted source judgment units')
    return normalized
