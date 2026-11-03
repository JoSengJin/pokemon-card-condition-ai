import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from card_condition import back_triage_cli as cli
from card_condition.back_triage_usage import entry_for, summarize


def fake_out(**change):
    parts = {p: dict(status='ranked') for p in ('edge', 'corner', 'surface')}
    parts['observation_limit'] = dict(status='scored')
    return dict(id='c1', results=parts, release_id='r', complete=False, **change)


class UsageTest(unittest.TestCase):
    def test_entry_has_no_paths_and_marks_outcomes(self):
        ok = entry_for(dict(id='c1', image='/secret/photo.jpg'), 0, fake_out(), 1.5, time.time())
        held = entry_for(dict(id='c2'), 0, dict(fake_out(fallback='existing_path'), results={'edge': dict(status='held', reason='x')}), 1.0, time.time())
        err = entry_for(None, 3, dict(status='held', reason='request_unreadable', fallback='existing_path'), .1, time.time())
        self.assertEqual(('ok', 'held', 'error'), (ok['outcome'], held['outcome'], err['outcome']))
        self.assertNotIn('/secret', json.dumps(ok))
        self.assertIsNone(err['request_id'])

    def test_summary_reports_thresholds_and_never_certifies(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d)/'u.jsonl'
            base = 1_800_000_000
            lines = [entry_for(dict(id=f'c{i % 60}'), 0 if i % 50 else 2, fake_out() if i % 50 else dict(status='held', reason='release_unavailable:x', fallback='existing_path'), 2.0, base + i * 6000) for i in range(120)]
            log.write_text('\n'.join(json.dumps(x) for x in lines) + '\n')
            s = summarize(log)
            self.assertEqual(120, s['measured']['requests'])
            self.assertEqual(60, s['measured']['unique_request_ids'])
            self.assertTrue(all(s['thresholds_met'][k] for k in ('days', 'cards', 'requests', 'p95')))
            self.assertFalse(s['thresholds_met']['errors'])
            self.assertFalse(s['pilot_certified'])
            self.assertTrue(s['not_computed'])

    def test_empty_or_foreign_log_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d)/'u.jsonl'
            log.write_text('')
            with self.assertRaises(ValueError):
                summarize(log)
            log.write_text(json.dumps(dict(kind='listing_predict_usage', total_seconds=1, started_unix=1)) + '\n')
            with self.assertRaises(ValueError):
                summarize(log)

    def test_cli_writes_one_record_per_call_and_summary_reads_it(self):
        with tempfile.TemporaryDirectory() as d:
            req, log = Path(d)/'r.json', Path(d)/'u.jsonl'
            req.write_text(json.dumps(dict(id='x', side='back', image='a.png', box=[0, 0, 1, 1], box_reviewed=True)))
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(['--release', str(Path(d)/'none.json'), '--request', str(req), '--usage-log', str(log)])
            self.assertEqual(2, code)
            rows = [json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual((1, 'error', 'x'), (len(rows), rows[0]['outcome'], rows[0]['request_id']))
            self.assertNotIn(str(d), log.read_text())
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, cli.main(['--summary', str(log)]))
            self.assertFalse(json.loads(out.getvalue())['pilot_certified'])


if __name__ == '__main__':
    unittest.main()
