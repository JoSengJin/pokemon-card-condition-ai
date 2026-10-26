"""Summarize a usage log against the measurable parts of the F2 pilot conditions; measurement only.

The summary never certifies a pilot: approval, deployment, physical-card identity, normal-card false
alarms and Gemini/review-time changes are outside this log and reported as not computed.
"""
from collections import defaultdict
import json
import math
from pathlib import Path

DAYS, CARDS, REQUESTS, P95_SECONDS, ERROR_RATE = 7, 50, 100, 30, .01
UNPINNED = 'unpinned (direct checkpoint)'
UNATTRIBUTED = 'unattributed (release requested, manifest unreadable)'
NOT_COMPUTED = ['normal-card false-alarm rate: needs >=30 human-verified fully normal cards',
                'Gemini call change and human review time: outside this log',
                'approved deployment and physical-card identity: request id is operator-attested, not verified',
                'hard crashes leave no record: pair the error rate with the consumer-side request count']


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


def release_group(key, entries, corrections):
    """Measured values and threshold checks for one release; None means not measurable, never passed."""
    ok = [e for e in entries if e['outcome'] == 'ok']
    warm_pairs = [e['analyze_seconds'] for e in ok if e['warm'] and e['faces'] == 2]
    span = max(e['started_unix'] for e in entries) - min(e['started_unix'] for e in entries)
    ids = {e['request_id'] for e in entries if e['request_id'] is not None}
    overlap = max_overlap(entries)
    p95_value = p95(warm_pairs)
    rate = (len(entries) - len(ok)) / len(entries)
    reviewed = [corrections[e['report_sha256']] for e in ok if e['report_sha256'] in corrections]
    return dict(release_id=key, pinned=key not in (UNPINNED, UNATTRIBUTED), requests=len(entries), ok=len(ok), errors=len(entries) - len(ok),
        requests_with_defect_warning=sum(e['cells']['defect'] > 0 for e in ok),
        requests_with_any_hold=sum(e['cells']['unknown'] > 0 for e in ok), human_review=dict(reviewed_requests=len(reviewed), requests_corrected=sum(r > 0 for r in reviewed),
                                          corrected_cells=sum(reviewed)),
        conditions=dict(
            span_days=dict(value=span / 86400, threshold=DAYS, met=span >= DAYS * 86400),
            requests=dict(value=len(entries), threshold=REQUESTS, met=len(entries) >= REQUESTS),
            distinct_request_ids=dict(value=len(ids), threshold=CARDS, met=len(ids) >= CARDS, identity_verified=False),
            warm_pair_p95_seconds=dict(value=p95_value, n=len(warm_pairs), threshold=P95_SECONDS, max_overlap=overlap,
                                       met=None if p95_value is None else p95_value <= P95_SECONDS and overlap == 1),
            recorded_error_rate=dict(value=rate, threshold=ERROR_RATE, met=rate <= ERROR_RATE)))


def summarize(log, reviews=()):
    """Group by release; review records link by exact report SHA and unmatched ones are counted, not guessed."""
    entries = read_lines(log, 'listing_predict_usage')
    if not entries:
        raise ValueError('Usage log has no records')
    corrections, incomplete = {}, 0
    for path in reviews:
        record = json.loads(Path(path).read_text())
        if type(record.get('report_sha256')) is not str or not isinstance(record.get('counts'), dict):
            raise ValueError(f'{path} is not a listing review record')
        if record.get('review_completed') is not True:
            incomplete += 1
            continue
        corrections[record['report_sha256']] = sum(record['counts'].get(k, 0) for k in ('corrected_defect', 'corrected_normal'))
    groups = defaultdict(list)
    for entry in entries:
        release = entry['release']
        key = (release['release_id'] if release else entry['attempted_release_id'] if entry['release_requested'] else UNPINNED)
        groups[key or UNATTRIBUTED].append(entry)
    linked = {e['report_sha256'] for e in entries if e['report_sha256']}
    return dict(schema_version=1, evaluation_kind='pilot_usage_summary', records=len(entries),
        releases=[release_group(k, v, corrections) for k, v in sorted(groups.items())],
        unmatched_review_records=sum(sha not in linked for sha in corrections), incomplete_review_records=incomplete, not_computed=NOT_COMPUTED,
        pilot_certified=False, independent=False)
