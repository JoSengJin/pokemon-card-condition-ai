"""Usage record and summary for assisted runs of the back triage CLI; measurement only, never certifies a pilot.

One JSON line per request (no photo path, no error text). Reuses the append-only writer and the F2 thresholds of the listing pilot tools."""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .pilot_record import append_line
from .pilot_summary import CARDS, DAYS, ERROR_RATE, P95_SECONDS, REQUESTS, p95

NOT_COMPUTED = ['normal-card false-alarm rate: needs >=30 human-verified fully normal cards (this suite gives priorities, not verdicts)',
                'Gemini call change and human review time: outside this log',
                'approved deployment and physical-card identity: request id is operator-attested',
                'every CLI call is a fresh process (cold); warm front+back pair latency is not measured (front is unsupported)',
                'hard crashes leave no record: pair the error rate with the consumer-side request count']


def entry_for(request, code, out, seconds, started):
    """Build one record from a finished CLI call; no paths or messages."""
    results = (out or {}).get('results', {})
    return dict(schema_version=1, kind='back_triage_usage', started_unix=started, started_at=datetime.fromtimestamp(started, timezone.utc).isoformat(),
                request_id=request.get('id') if isinstance(request, dict) and type(request.get('id')) is str else None, total_seconds=seconds,
                outcome='ok' if code == 0 and not (out or {}).get('fallback') else 'held' if code == 0 else 'error', exit_code=code,
                release_id=(out or {}).get('release_id'), reason=(out or {}).get('reason'),
                parts={name: dict(status=r['status'], reason=r.get('reason')) for name, r in results.items()}, fallback=(out or {}).get('fallback'))


def record(path, entry):
    """Append one line; a record that cannot be written raises so the call is not counted as a success."""
    if path is not None:
        append_line(path, entry)


def summarize(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows or any(r.get('kind') != 'back_triage_usage' or type(r.get('total_seconds')) not in (int, float) or not math.isfinite(r['total_seconds']) for r in rows):
        raise ValueError('Usage log is empty or has a record of another kind or invalid timing')
    starts, ids = [r['started_unix'] for r in rows], {r['request_id'] for r in rows if r['request_id']}
    errors, days = sum(r['outcome'] == 'error' for r in rows), (max(starts) - min(starts)) / 86400
    reasons = Counter(p['reason'] for r in rows for p in r['parts'].values() if p['status'] == 'held' and p.get('reason'))
    measured = dict(requests=len(rows), unique_request_ids=len(ids), span_days=days, cold_p95_seconds=p95([r['total_seconds'] for r in rows]), error_rate=errors/len(rows),
                    held_requests=sum(r['outcome'] == 'held' for r in rows), hold_reasons=dict(reasons), releases=dict(Counter(r.get('release_id') for r in rows)))
    met = dict(days=days >= DAYS, cards=len(ids) >= CARDS, requests=len(rows) >= REQUESTS, p95=measured['cold_p95_seconds'] <= P95_SECONDS, errors=measured['error_rate'] <= ERROR_RATE)
    return dict(measured=measured, thresholds_met=met, not_computed=NOT_COMPUTED, pilot_certified=False)
