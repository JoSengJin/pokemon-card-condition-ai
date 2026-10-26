"""Append-only usage record for assisted/shadow listing runs; measurement only, never a verdict.

One JSON line per request: timings, outcome, hold/defect cell counts and the release. No photo paths
and no error messages (they can contain paths). A record that cannot be written fails the request so
that an unrecorded run is never counted as a pilot success.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

PRINTED = dict(ensure_ascii=False, indent=2, allow_nan=False)


def append_line(path, entry):
    """Single O_APPEND write plus fsync: concurrent processes cannot interleave a line."""
    line = (json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


class UsageRecorder:
    """No-op when path is None. One recorder per process: a request is warm after one finished request."""

    def __init__(self, path, release_manifest=None):
        self.path, self.release_manifest, self.completed, self.began = path, release_manifest, 0, None

    def start(self, request):
        self.began, self.clock = time.time(), time.perf_counter()
        self.analysis_clock = self.clock
        self.loaded_seconds = None
        ok = isinstance(request, dict)
        self.request_id = request.get('id') if ok and type(request.get('id')) is str else None
        self.faces = sum(isinstance(request.get(side), dict) for side in ('front', 'back')) if ok else 0

    def loaded(self):
        self.analysis_clock = time.perf_counter()
        self.loaded_seconds = self.analysis_clock - self.clock

    def entry(self, outcome, error_type=None, report=None):
        end = time.perf_counter()
        entry = dict(schema_version=1, kind='listing_predict_usage', outcome=outcome, error_type=error_type,
                     started_unix=self.began, request_id=self.request_id, faces=self.faces,
                     started_at=datetime.fromtimestamp(self.began, timezone.utc).isoformat(),
                     total_seconds=end - self.clock, load_seconds=self.loaded_seconds,
                     analyze_seconds=end - self.analysis_clock if report is not None else None,
                     warm=self.completed > 0, release_requested=self.release_manifest is not None,
                     attempted_release_id=None, release=None, model_sha256=None, device=None, image_size=None,
                     batched_views=None, report_sha256=None, cells=None, hold_reasons=None)
        if self.release_manifest is not None:
            try:  # best effort: a failed run must still be attributable to the release it tried to use
                attempted = json.loads(Path(self.release_manifest).read_text()).get('release_id')
                entry['attempted_release_id'] = attempted if type(attempted) is str else None
            except (OSError, ValueError, AttributeError):
                pass
        if report is not None:
            cells = report['listing_readiness']['records'][0]['cells']
            states = Counter(c['state'] for c in cells)
            entry.update(release=report.get('release'), model_sha256=report['model_sha256'],
                         device=report['device'], image_size=report['image_size'],
                         batched_views=report['batched_views'],
                         report_sha256=hashlib.sha256((json.dumps(report, **PRINTED) + '\n').encode()).hexdigest(),
                         cells=dict(normal=states['normal'], defect=states['defect'], unknown=states['unknown']),
                         hold_reasons=dict(Counter(c['reason'] for c in cells if c['state'] == 'unknown')))
        if not all(math.isfinite(entry[k]) for k in ('total_seconds', 'started_unix')):
            raise ValueError('Non-finite usage timing')
        return entry

    def finish(self, report):
        if self.path is not None:
            append_line(self.path, self.entry('ok', report=report))
        self.completed, self.began = self.completed + 1, None

    def fail(self, exc):
        if self.path is None:
            return
        if self.began is None:  # failed before the request was read
            self.start(None)
        append_line(self.path, self.entry('error', error_type=type(exc).__name__))
        self.began = None
