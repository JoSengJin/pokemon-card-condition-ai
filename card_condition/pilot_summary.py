"""Summarize a usage log against the measurable parts of the F2 pilot conditions; measurement only.

The summary never certifies a pilot: approval, deployment, physical-card identity, normal-card false
alarms and Gemini/review-time changes are outside this log and reported as not computed.
"""
from collections import defaultdict
import json
import math
import re
from pathlib import Path

DAYS, CARDS, REQUESTS, P95_SECONDS, ERROR_RATE = 7, 50, 100, 30, .01
UNPINNED = 'unpinned (direct checkpoint)'
UNATTRIBUTED = 'unattributed (release requested, manifest unreadable)'
NOT_COMPUTED = ['normal-card false-alarm rate: needs >=30 human-verified fully normal cards',
                'Gemini call change and human review time: outside this log',
                'approved deployment and physical-card identity: request id is operator-attested, not verified',
                'hard crashes leave no record: pair the error rate with the consumer-side request count',
                'hardware identity and original photo dimensions are not verified by device/image_size metadata',
                'a failed attempt with only a release label cannot establish the exact release manifest']
SHA = re.compile('[0-9a-f]{64}')


def read_lines(path, kind):
    """Strict JSONL: every non-empty line must parse and match the schema; otherwise reject the whole file."""
    rows = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or row.get('kind') != kind or row.get('schema_version') != 1:
            raise ValueError(f'{path}:{number} is not a schema-1 {kind} record')
        rows.append(row)
    return rows


def p95(values):
    """Nearest rank, the same rule as card_condition.benchmark; None for no samples."""
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


def max_overlap(entries):
    """Peak number of requests in flight, from start and total seconds."""
    edges = sorted([(e['started_unix'], 1) for e in entries] + [(e['started_unix'] + e['total_seconds'], -1) for e in entries],
                   key=lambda edge: (edge[0], edge[1]))
    peak = current = 0
    for _, step in edges:
        current += step
        peak = max(peak, current)
    return peak


def validate_usage(entry):
    """Reject impossible arithmetic before producing any numeric condition; missing pins stay unknown."""
    required = {'release', 'attempted_release_id', 'request_id', 'report_sha256', 'analyze_seconds', 'cells'}
    if not required <= set(entry) or type(entry.get('schema_version')) is not int:
        raise ValueError('Incomplete usage record')
    if entry.get('release') and entry.get('release_requested') is False:
        raise ValueError('Usage release conflicts with the requested mode')
    if entry.get('outcome') not in ('ok', 'error') or type(entry.get('warm')) is not bool or type(entry.get('release_requested')) is not bool:
        raise ValueError('Invalid usage outcome or flags')
    for field in ('started_unix', 'total_seconds'):
        value = entry.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Usage timings must be finite non-negative numbers')
    if type(entry.get('faces')) is not int or not 0 <= entry['faces'] <= 2:
        raise ValueError('Invalid usage face count')
    if (entry.get('request_id') is not None and type(entry['request_id']) is not str
            or entry.get('release') is not None and not isinstance(entry['release'], dict)
            or entry.get('attempted_release_id') is not None and type(entry['attempted_release_id']) is not str):
        raise ValueError('Invalid usage identity')
    if entry['outcome'] == 'ok':
        value, cells = entry.get('analyze_seconds'), entry.get('cells')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= entry['total_seconds']:
            raise ValueError('Invalid successful analysis duration')
        if (not isinstance(cells, dict) or set(cells) != {'normal', 'defect', 'unknown'}
                or any(type(v) is not int or v < 0 for v in cells.values()) or type(entry.get('report_sha256')) is not str):
            raise ValueError('Invalid successful usage cells or result identity')
        release = entry.get('release') or {}
        region = release.get('checkpoint_sha256', {}).get('region') if isinstance(release.get('checkpoint_sha256'), dict) else None
        if (type(region) is str and SHA.fullmatch(region) and entry.get('model_sha256') is not None
                and entry['model_sha256'] != region):
            raise ValueError('Usage model SHA differs from its pinned release')


def configuration_state(entries):
    """Keep declared configurations separate; do not pick a fast cohort or guess missing metadata."""
    cohorts, unknown = defaultdict(list), 0
    for entry in entries:
        device, size, batched = entry.get('device'), entry.get('image_size'), entry.get('batched_views')
        if type(device) is not str or device not in ('cpu', 'mps') or type(size) is not int or size not in (224, 448) or type(batched) is not bool:
            unknown += 1
            continue
        cohorts[device, size, batched].append(entry)
    status = 'mixed' if len(cohorts) > 1 else 'incomplete' if unknown or not cohorts else 'fixed'
    return dict(status=status, met=False if status == 'mixed' else True if status == 'fixed' else None,
                unknown_successful_records=unknown, hardware_identity_verified=False,
                cohorts=[dict(device=device, image_size=size, batched_views=batched, requests=len(rows),
                              warm_pairs=sum(e['warm'] and e['faces'] == 2 for e in rows),
                              warm_pair_p95_seconds=p95([e['analyze_seconds'] for e in rows if e['warm'] and e['faces'] == 2]))
                         for (device, size, batched), rows in sorted(cohorts.items())])


def release_group(key, entries, corrections):
    """Label-level diagnostics; F2 numeric gates require exact release pins and one declared configuration."""
    ok = [e for e in entries if e['outcome'] == 'ok']
    identities, unidentified = {}, 0
    required = ('release_id', 'package_version', 'input_contract', 'manifest_sha256', 'checkpoint_sha256')
    for entry in entries:
        release = entry.get('release')
        if (not isinstance(release, dict) or not set(required) <= set(release)
                or any(type(release[k]) is not str or not release[k].strip() for k in required[:-1])
                or release['input_contract'] != 'listing-request-v1' or not SHA.fullmatch(release['manifest_sha256'])
                or not isinstance(release['checkpoint_sha256'], dict) or 'region' not in release['checkpoint_sha256']
                or set(release['checkpoint_sha256']) - {'region', 'observation', 'recall'}
                or any(type(v) is not str or not SHA.fullmatch(v) for v in release['checkpoint_sha256'].values())
                or entry['outcome'] == 'ok' and entry.get('model_sha256') != release['checkpoint_sha256']['region']):
            unidentified += 1
            continue
        identity = {k: release[k] for k in required}
        identities[json.dumps(identity, sort_keys=True)] = identity
    identity_status = 'conflict' if len(identities) > 1 else 'consistent' if len(identities) == 1 and not unidentified else 'incomplete'
    pinned = identity_status == 'consistent'
    config = configuration_state(ok)
    warm_pairs = [e['analyze_seconds'] for e in ok if e['warm'] and e['faces'] == 2]
    span = max(e['started_unix'] for e in entries) - min(e['started_unix'] for e in entries)
    ids = {e['request_id'] for e in entries if type(e.get('request_id')) is str and e['request_id'].strip()}
    overlap = max_overlap(entries)
    p95_value = p95(warm_pairs) if pinned and config['status'] == 'fixed' else None
    rate = (len(entries) - len(ok)) / len(entries)
    reviewed = [corrections[e['report_sha256']] for e in ok if e['report_sha256'] in corrections]
    conditions = dict(
        span_days=dict(value=span / 86400, threshold=DAYS, met=span >= DAYS * 86400),
        requests=dict(value=len(entries), threshold=REQUESTS, met=len(entries) >= REQUESTS),
        distinct_request_ids=dict(value=len(ids), threshold=CARDS, met=len(ids) >= CARDS, identity_verified=False),
        warm_pair_p95_seconds=dict(value=p95_value, n=len(warm_pairs), threshold=P95_SECONDS, max_overlap=overlap,
                                   met=False if config['status'] == 'mixed' else None if p95_value is None else p95_value <= P95_SECONDS and overlap == 1),
        recorded_error_rate=dict(value=rate, threshold=ERROR_RATE, met=rate <= ERROR_RATE))
    if not pinned:
        for condition in conditions.values():
            condition['met'] = False if identity_status == 'conflict' else None
    conditions.update(fixed_release_identity=dict(met=pinned if identity_status != 'incomplete' else None,
                                                  status=identity_status, unidentified_records=unidentified),
                      fixed_declared_execution_configuration=config)
    return dict(release_id=key, pinned=pinned, grouping='release_id label diagnostics', release_identity_status=identity_status,
        release_identity_variants=[identities[k] for k in sorted(identities)],
        requests=len(entries), ok=len(ok), errors=len(entries) - len(ok),
        requests_with_defect_warning=sum(e['cells']['defect'] > 0 for e in ok),
        requests_with_any_hold=sum(e['cells']['unknown'] > 0 for e in ok),
        human_review=dict(reviewed_requests=len(reviewed), requests_corrected=sum(r > 0 for r in reviewed), corrected_cells=sum(reviewed)),
        conditions=conditions)


def summarize(log, reviews=()):
    """Group by release; review records link by exact report SHA and unmatched ones are counted, not guessed."""
    entries = read_lines(log, 'listing_predict_usage')
    if not entries:
        raise ValueError('Usage log has no records')
    corrections, completed_counts, incomplete = {}, {}, 0
    for path in reviews:
        record = json.loads(Path(path).read_text())
        if (not isinstance(record, dict) or type(record.get('report_sha256')) is not str
                or not record['report_sha256'].strip() or type(record.get('review_completed')) is not bool
                or not isinstance(record.get('counts'), dict)
                or not {'corrected_defect', 'corrected_normal'} <= set(record['counts'])
                or any(type(v) is not int or v < 0 for v in record['counts'].values())):
            raise ValueError(f'{path} is not a listing review record with non-negative integer counts')
        if record.get('review_completed') is not True:
            incomplete += 1
            continue
        sha, counts = record['report_sha256'], record['counts']
        if sha in completed_counts and completed_counts[sha] != counts:
            raise ValueError('Conflicting completed reviews for the same report SHA; choose the adjudicated review explicitly')
        completed_counts[sha] = counts
        corrections[sha] = counts['corrected_defect'] + counts['corrected_normal']
    groups = defaultdict(list)
    for entry in entries:
        validate_usage(entry)
        release = entry['release']
        key = (release.get('release_id') if release else entry['attempted_release_id'] if entry['release_requested'] else UNPINNED)
        if type(key) is not str or not key.strip():
            key = UNATTRIBUTED
        groups[key or UNATTRIBUTED].append(entry)
    linked = {e['report_sha256'] for e in entries if e['report_sha256']}
    return dict(schema_version=1, evaluation_kind='pilot_usage_summary', records=len(entries),
        releases=[release_group(k, v, corrections) for k, v in sorted(groups.items())],
        unmatched_review_records=sum(sha not in linked for sha in corrections), incomplete_review_records=incomplete, not_computed=NOT_COMPUTED,
        pilot_certified=False, independent=False)
