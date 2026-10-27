"""Bind saved listing results to one release and original photo requests; never infer."""
import hashlib
import json
import math
from pathlib import Path
import re

from .listing_model import photo_request
from .listing_readiness import listing_readiness
from .regions import GLARE_AREAS, REGION_LABELS, REGION_TARGET_AREAS, region_box


def pinned_json(path, expected, hashes):
    path = Path(path).resolve()
    raw = path.read_bytes()
    if (type(expected) is not str or not re.fullmatch('[0-9a-f]{64}', expected)
            or hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('Pinned input SHA256 mismatch')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Pinned JSON input must be an object')
    hashes[str(path)] = expected
    return result


def bundle_cases(bundle, records):
    if (set(bundle) != {'schema_version', 'manifest_sha256', 'release_sha256', 'cases'}
            or type(bundle['schema_version']) is not int or bundle['schema_version'] != 1
            or not isinstance(bundle['cases'], list)):
        raise ValueError('Invalid coverage bundle')
    known, found = {r['id'] for r in records}, {}
    for case in bundle['cases']:
        if (not isinstance(case, dict) or set(case) != {'id', 'request', 'report'}
                or type(case['id']) is not str or case['id'] not in known or case['id'] in found):
            raise ValueError('Additional, duplicate or invalid listing case')
        for kind in ('request', 'report'):
            entry = case[kind]
            if (not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}
                    or type(entry['path']) is not str or not entry['path']):
                raise ValueError('Each listing input requires its original path and SHA256')
        found[case['id']] = case
    return found


def checked_case(source, request, report, release, supported, hashes):
    row, unreviewed = photo_request(request)
    if (row['id'] != source['id'] or report.get('id') != source['id'] or report.get('release') != release
            or report.get('model_sha256') != release['checkpoint_sha256']['region']):
        raise ValueError('Listing result does not match the pinned source and release')
    for role, field in (('observation', 'observation_evidence'), ('recall', 'recall_review')):
        expected_sha, block = release['checkpoint_sha256'].get(role), report.get(field)
        if (expected_sha is None and block is not None or expected_sha is not None
                and (not isinstance(block, dict) or block.get('model_sha256') != expected_sha)):
            raise ValueError('Auxiliary model differs from pinned release')
    expected_photos, expected = {}, set()
    for side, annotation in row['side_annotations'].items():
        face = source.get('side_annotations', {}).get(side, {})
        if not source.get(side) or Path(row[side]).resolve() != Path(source[side]).resolve():
            raise ValueError('Request photo differs from frozen human source')
        if annotation['box'] is not None and annotation['box'] != face.get('box'):
            raise ValueError('Request geometry differs from frozen human source')
        for field in ('visibility_issues', 'glare_areas'):
            if field in request[side] and field in face and request[side][field] != face[field]:
                raise ValueError('Request observation review differs from frozen human source')
        expected_photos[row[side]] = hashes[str(Path(row[side]).resolve())]
        issues, glare = annotation['visibility_issues'], annotation['glare_areas']
        if annotation['box'] is None or side in unreviewed or set(issues) - {'glare'}:
            continue
        expected.update((side, area) for area in GLARE_AREAS
                        if any(area in REGION_TARGET_AREAS[q] for q in supported)
                        and not ('glare' in issues and (not glare or area in glare)))
    if report.get('input_photo_sha256') != expected_photos or report.get('observation_unreviewed_sides') != unreviewed:
        raise ValueError('Saved photo identity or observation-review scope mismatch')
    predictions = report.get('predictions')
    if not isinstance(predictions, list):
        raise ValueError('Missing listing predictions')
    seen = set()
    for item in predictions:
        if (not isinstance(item, dict) or set(item) != {'card_id', 'group', 'side', 'image', 'card_box', 'area', 'box', 'probabilities'}
                or type(item['side']) is not str or type(item['area']) is not str):
            raise ValueError('Invalid listing prediction')
        key = item['side'], item['area']
        if key not in expected or key in seen:
            raise ValueError('Additional, duplicate or unmatched listing prediction')
        seen.add(key)
        annotation = row['side_annotations'][item['side']]
        if (item['card_id'] != row['id'] or item['group'] != row['id'] or item['image'] != row[item['side']]
                or item['card_box'] != annotation['box'] or item['box'] != region_box(annotation['box'], item['area'])):
            raise ValueError('Listing prediction identity or geometry mismatch')
        probs = item['probabilities']
        if not isinstance(probs, dict) or set(probs) != set(REGION_LABELS):
            raise ValueError('Invalid listing probability scope')
        for label, score in probs.items():
            applicable = label in supported and item['area'] in REGION_TARGET_AREAS[label]
            if (applicable and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1)
                    or not applicable and score is not None):
                raise ValueError('Invalid, missing or unsupported listing score')
    if seen != expected:
        raise ValueError('Saved listing omitted inference cells')
    readiness = listing_readiness([row], predictions, supported, unreviewed_sides=unreviewed)
    if json.dumps(report.get('listing_readiness'), sort_keys=True, allow_nan=False) != json.dumps(readiness, sort_keys=True, allow_nan=False):
        raise ValueError('Saved listing state, hold reason or policy differs from recomputation')
    return {(c['side'], c['area'], c['label']): c for c in readiness['records'][0]['cells']}
