"""Opt-in input sealing and conservative, checkout-local one-use test receipts.

This is an integrity/exposure guard. Human grouping, complete usage history, D1 coverage
and the timing of candidate selection still require independent evidence.
"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re

from .evaluation_output import write_new_report
from .release import file_sha256

LEDGER = Path(__file__).resolve().parents[1] / 'artifacts/frozen-test-usage'
SHA = re.compile('[0-9a-f]{64}')


def seal_test(manifest, history, output):
    """Freeze a test-only manifest and supplied development history, without modifying truth."""
    from .data import load_manifest
    from .evaluation_inputs import track_photos, reject_copied_test_groups, unchanged_inputs

    manifest, output = Path(manifest).resolve(), Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new seal path')
    histories = [Path(p).resolve() for p in history]
    if not histories or len(histories) != len(set(histories)) or manifest in histories:
        raise ValueError('Distinct development history manifests are required')
    hashes = {str(p): file_sha256(p) for p in (manifest, *histories)}
    records = load_manifest(manifest, require_gradable=False)
    if any(row['split'] != 'test' for row in records):
        raise ValueError('Seal requires a separate test-only manifest')
    photo_sides = {}
    for row in records:
        if row.get('excluded'):
            continue
        for side, digest in zip((s for s in ('front', 'back') if row.get(s)), row['_image_hashes']):
            if photo_sides.setdefault(digest, side) != side:
                raise ValueError('Same decoded photo is assigned to both front and back')
    reject_copied_test_groups(records)
    track_photos(records, hashes)
    ids, groups, pixels = ({r['id'] for r in records}, {r['group'] for r in records},
                           {h for r in records for h in r['_image_hashes']})
    for path in histories:
        used = load_manifest(path, require_gradable=False)
        track_photos(used, hashes)
        if (ids & {r['id'] for r in used} or groups & {r['group'] for r in used}
                or pixels & {h for r in used for h in r['_image_hashes']}):
            raise ValueError('Test cards or photos were present in supplied usage history')
    truth = [dict(id=r['id'], group=r['group'], labels=r['labels'],
                  side_annotations=r.get('side_annotations')) for r in records]
    grouping = [dict(id=r['id'], group=r['group'], decoded_photo_sha256=r['_image_hashes']) for r in records]
    report = dict(schema_version=1, kind='frozen_test_inputs',
                  sealed_at=datetime.now(timezone.utc).isoformat(), manifest=str(manifest),
                  manifest_sha256=hashes[str(manifest)], history=[str(p) for p in histories],
                  input_hashes=hashes, physical_groups=sorted(groups), decoded_photo_sha256=sorted(pixels),
                  truth_sha256=hashlib.sha256(json.dumps(truth, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                  grouping_sha256=hashlib.sha256(json.dumps(grouping, sort_keys=True).encode()).hexdigest(),
                  d1_verified=False, d2_verified=False,
                  limitations=['Only supplied usage history is checked; human physical grouping and unused status require review.',
                               'No D1 quantity, subgroup, provenance or pre-selection timing certification.',
                               'Use the returned file SHA at evaluation; keep the checkout usage ledger across runs.'])
    unchanged_inputs(hashes)
    write_new_report(output, report)
    return report


def read_seal(path, expected_sha256, manifest):
    """Verify the caller-pinned seal and every input byte before reserving any test use."""
    path = Path(path).resolve()
    if type(expected_sha256) is not str or not SHA.fullmatch(expected_sha256):
        raise ValueError('Expected test seal SHA256 is required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Test seal SHA256 mismatch')
    seal = json.loads(raw)
    if (not isinstance(seal, dict) or seal.get('schema_version') != 1 or seal.get('kind') != 'frozen_test_inputs'
            or seal.get('manifest') != str(Path(manifest).resolve())
            or not isinstance(seal.get('input_hashes'), dict) or not seal['input_hashes']
            or seal['input_hashes'].get(seal['manifest']) != seal.get('manifest_sha256')
            or not isinstance(seal.get('history'), list) or not seal['history']
            or any(type(p) is not str or p not in seal['input_hashes'] for p in seal['history'])
            or any(not isinstance(seal.get(k), list) or not seal[k] or
                   any(type(v) is not str or not v.strip() for v in seal[k])
                   for k in ('physical_groups', 'decoded_photo_sha256'))
            or any(not SHA.fullmatch(v) for v in seal['decoded_photo_sha256'])):
        raise ValueError('Invalid test seal identity')
    for name, expected in seal['input_hashes'].items():
        if (type(name) is not str or not Path(name).is_absolute() or type(expected) is not str
                or not SHA.fullmatch(expected) or file_sha256(name) != expected):
            raise ValueError('Frozen test input changed')
    return seal, dict(seal['input_hashes'], **{str(path): expected_sha256})


def claim_test(path, expected_sha256, manifest, checkpoint, operation, *,
               candidate_path=None, candidate_sha256=None, device=None):
    """Reserve before inference. A subsequent failure retains this exposure claim, without retry."""
    if path is None and expected_sha256 is None and candidate_path is None and candidate_sha256 is None:
        return None
    if path is None or expected_sha256 is None:
        raise ValueError('Test seal and its expected SHA256 must be supplied together')
    seal, hashes = read_seal(path, expected_sha256, manifest)
    candidate = None
    if candidate_path is not None or candidate_sha256 is not None:
        from .frozen_candidate import read_candidate
        if candidate_path is None or candidate_sha256 is None:
            raise ValueError('Candidate and its SHA256 must be supplied together')
        candidate, candidate_hashes = read_candidate(candidate_path, candidate_sha256, expected_sha256, checkpoint, operation, device)
        hashes.update(candidate_hashes)
    receipt = dict(schema_version=1, kind='frozen_test_use', status='exposure_claimed',
                   claimed_at=datetime.now(timezone.utc).isoformat(), operation=operation,
                   seal_sha256=expected_sha256, candidate_sha256=candidate_sha256, manifest_sha256=seal['manifest_sha256'],
                   model_sha256=file_sha256(checkpoint), physical_groups=seal['physical_groups'],
                   decoded_photo_sha256=seal['decoded_photo_sha256'])
    LEDGER.mkdir(parents=True, exist_ok=True)
    with (LEDGER / 'usage.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for previous in LEDGER.glob('*.json'):
            used = json.loads(previous.read_text())
            if (not isinstance(used, dict) or used.get('kind') != 'frozen_test_use'
                    or not isinstance(used.get('physical_groups'), list)
                    or not isinstance(used.get('decoded_photo_sha256'), list)):
                raise ValueError('Invalid existing test usage receipt; manual audit required')
            if (set(used['physical_groups']) & set(seal['physical_groups'])
                    or set(used['decoded_photo_sha256']) & set(seal['decoded_photo_sha256'])):
                if not (candidate is not None and used.get('candidate_sha256') == candidate_sha256
                        and used.get('seal_sha256') == expected_sha256
                        and used.get('operation') in candidate['models'] and used['operation'] != operation):
                    raise ValueError('Frozen test cards or photos already used; no automatic retry')
        suffix = '-' + operation if candidate is not None else ''
        target = LEDGER / (expected_sha256 + suffix + '.json')
        write_new_report(target, receipt)
    return dict(seal_sha256=expected_sha256, candidate_sha256=candidate_sha256, operation=operation,
                receipt_sha256=file_sha256(target),
                receipt=str(target), status='exposure_claimed', input_hashes=hashes)
