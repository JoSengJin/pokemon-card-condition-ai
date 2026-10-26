from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.cli import main
from card_condition.listing_model import ListingAnalyzer
from card_condition.pilot_record import UsageRecorder
from test_release import fixture_release


def run(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with patch('sys.argv', ['card-condition', 'listing-predict', *argv, '--device', 'cpu']), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            main()
        except SystemExit as exc:
            code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()


class PilotRecordTest(unittest.TestCase):
    def test_success_record_matches_printed_report_and_hides_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, _ = fixture_release(root)
            log, request = root/'usage.jsonl', str(root/'request.json')
            code, stdout, _ = run([request, '--release', str(manifest), '--usage-log', str(log)])
            self.assertEqual(0, code)
            entries = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(1, len(entries))
            entry, report = entries[0], json.loads(stdout)
            self.assertEqual(hashlib.sha256(stdout.encode()).hexdigest(), entry['report_sha256'])
            self.assertEqual(('ok', 'one', 1, False), (entry['outcome'], entry['request_id'], entry['faces'], entry['warm']))
            self.assertEqual(report['release'], entry['release'])
            cells = report['listing_readiness']['records'][0]['cells']
            self.assertEqual(len(cells), sum(entry['cells'].values()))
            self.assertEqual(entry['cells']['unknown'], sum(entry['hold_reasons'].values()))
            self.assertIsNotNone(entry['load_seconds'])
            self.assertLessEqual(entry['analyze_seconds'], entry['total_seconds'])
            self.assertNotIn(str(root), log.read_text())
            code, plain, _ = run([request, '--release', str(manifest)])
            self.assertEqual((0, stdout), (code, plain))
            self.assertEqual(1, len(log.read_text().splitlines()))

    def test_failures_are_recorded_without_messages_and_never_print_a_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, checkpoint = fixture_release(root)
            log, request = root/'usage.jsonl', str(root/'request.json')
            bad = json.loads(manifest.read_text())
            bad['package_version'] = '0.0.1'
            (root/'old.json').write_text(json.dumps(bad))
            for argv in ([request, '--release', str(root/'old.json')], [str(root/'missing.json'), '--release', str(manifest)],
                         [request, '--release', str(root/'absent.json')]):
                code, stdout, stderr = run([*argv, '--usage-log', str(log)])
                self.assertEqual((1, ''), (code, stdout))
                self.assertTrue(json.loads(stderr)['requires_gemini'])
            entries = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(['error'] * 3, [e['outcome'] for e in entries])
            self.assertEqual(['ValueError', 'FileNotFoundError', 'FileNotFoundError'], [e['error_type'] for e in entries])
            self.assertEqual(['one', None, 'one'], [e['request_id'] for e in entries])
            self.assertEqual(['fixture-0', 'fixture-0', None], [e['attempted_release_id'] for e in entries])
            self.assertTrue(all(e['release_requested'] and e['release'] is None for e in entries))
            self.assertTrue(all(e['report_sha256'] is None and e['cells'] is None for e in entries))
            self.assertNotIn('0.0.1', log.read_text())

    def test_unwritable_log_fails_the_request_instead_of_counting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, _ = fixture_release(root)
            code, stdout, stderr = run([str(root/'request.json'), '--release', str(manifest), '--usage-log', str(root)])
            self.assertEqual((1, ''), (code, stdout))
            self.assertTrue(json.loads(stderr)['requires_gemini'])

    def test_second_request_in_one_process_is_warm_and_skips_load_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, _ = fixture_release(root)
            request = json.loads((root/'request.json').read_text())
            log = root/'usage.jsonl'
            analyzer, recorder = ListingAnalyzer(release=manifest, device='cpu'), UsageRecorder(str(log))
            for _ in range(2):
                recorder.start(request)
                recorder.finish(analyzer.analyze(request))
            first, second = (json.loads(line) for line in log.read_text().splitlines())
            self.assertEqual((False, True), (first['warm'], second['warm']))
            self.assertIsNone(second['load_seconds'])
            self.assertGreater(second['analyze_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
