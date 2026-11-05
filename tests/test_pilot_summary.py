from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.cli import main
from card_condition.pilot_summary import max_overlap, p95, summarize

DAY = 86400


def entry(at, index=0, outcome='ok', warm=True, faces=2, release='r1', seconds=5., analyze=4., defect=0, unknown=3):
    """A hand-built schema-1 usage record; every number here is a test input, not a measurement."""
    ok = outcome == 'ok'
    digest = hashlib.sha256((release or 'direct').encode()).hexdigest()
    pinned = dict(release_id=release, package_version='fixture', input_contract='listing-request-v1',
                  manifest_sha256=digest, checkpoint_sha256={'region': digest}) if release else None
    return dict(schema_version=1, kind='listing_predict_usage', outcome=outcome, error_type=None if ok else 'ValueError',
                started_unix=at, request_id=f'card-{index}', faces=faces, started_at='x', total_seconds=max(seconds, analyze) if ok else seconds,
                load_seconds=None, analyze_seconds=analyze if ok else None, warm=warm,
                release=pinned, release_requested=release is not None, model_sha256=digest if ok else None,
                device='cpu' if ok else None, image_size=224 if ok else None, batched_views=False if ok else None,
                attempted_release_id=release, report_sha256=f'sha-{index}' if ok else None,
                cells=dict(normal=10, defect=defect, unknown=unknown) if ok else None)


def write(root, entries):
    path = root/'usage.jsonl'
    path.write_text(''.join(json.dumps(e) + '\n' for e in entries))
    return path


class PilotSummaryTest(unittest.TestCase):
    def test_p95_is_nearest_rank_and_overlap_counts_concurrent_requests(self):
        self.assertEqual(19, p95(list(range(1, 21))))
        self.assertEqual(95, p95(list(range(1, 101))[::-1]))
        self.assertEqual(20, p95(list(range(1, 22))))
        self.assertIsNone(p95([]))
        self.assertEqual(1, max_overlap([entry(0, seconds=5), entry(5, 1, seconds=5)]))
        self.assertEqual(2, max_overlap([entry(0, seconds=5), entry(4.9, 1, seconds=5)]))

    def test_condition_boundaries_and_warm_pair_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            steps = [entry(i * 7 * DAY / 99, i, analyze=30.) for i in range(100)]
            group = summarize(write(root, steps))['releases'][0]['conditions']
            self.assertEqual((7., True, 100, True), (group['span_days']['value'], group['span_days']['met'],
                                                    group['requests']['value'], group['requests']['met']))
            self.assertEqual((30., True, 100), (group['warm_pair_p95_seconds']['value'], group['warm_pair_p95_seconds']['met'],
                                                group['warm_pair_p95_seconds']['n']))
            self.assertEqual((100, True, False), (group['distinct_request_ids']['value'], group['distinct_request_ids']['met'],
                                                  group['distinct_request_ids']['identity_verified']))
            short = summarize(write(root, steps[:99]))['releases'][0]['conditions']
            self.assertFalse(short['requests']['met'])
            slow = summarize(write(root, [entry(i * 10, i, analyze=30.01) for i in range(5)]))['releases'][0]['conditions']
            self.assertFalse(slow['warm_pair_p95_seconds']['met'])
            cold = summarize(write(root, [entry(i * 10, i, warm=False) for i in range(3)] + [entry(99, 9, faces=1)]))
            self.assertIsNone(cold['releases'][0]['conditions']['warm_pair_p95_seconds']['met'])
            overlapped = summarize(write(root, [entry(0, 0), entry(1, 1)]))['releases'][0]['conditions']
            self.assertFalse(overlapped['warm_pair_p95_seconds']['met'])

    def test_error_rate_boundary_and_releases_are_never_merged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = [entry(i * 10, i) for i in range(99)] + [entry(2000, 99, outcome='error')]
            rows += [entry(3000 + i * 10, 200 + i, release='r2') for i in range(2)] + [entry(4000, 300, release=None)]
            lost = entry(5000, 400, outcome='error')
            lost['attempted_release_id'] = None
            lost['release'] = None
            report = summarize(write(root, rows + [lost]))
            by_id = {g['release_id']: g for g in report['releases']}
            self.assertEqual(['r1', 'r2', 'unattributed (release requested, manifest unreadable)',
                              'unpinned (direct checkpoint)'], sorted(by_id))
            self.assertEqual((False, 1), (by_id['unattributed (release requested, manifest unreadable)']['pinned'],
                                          by_id['unattributed (release requested, manifest unreadable)']['errors']))
            first = by_id['r1']
            self.assertEqual((100, 99, 1), (first['requests'], first['ok'], first['errors']))
            self.assertEqual((.01, True), (first['conditions']['recorded_error_rate']['value'],
                                           first['conditions']['recorded_error_rate']['met']))
            self.assertFalse(by_id['unpinned (direct checkpoint)']['pinned'])
            rows.append(entry(2100, 98, outcome='error'))
            self.assertFalse({g['release_id']: g for g in summarize(write(root, rows))['releases']}['r1']
                             ['conditions']['recorded_error_rate']['met'])
            self.assertFalse(report['pilot_certified'])
            self.assertTrue(any('false-alarm' in item for item in report['not_computed']))

    def test_reviews_link_by_exact_report_sha_and_incomplete_ones_are_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = write(root, [entry(0, 0, defect=1), entry(10, 1), entry(20, 2)])
            reviews = []
            for name, sha, complete, corrected in (('a.json', 'sha-0', True, 2), ('b.json', 'sha-1', True, 0),
                                                   ('c.json', 'sha-2', False, 0), ('d.json', 'sha-unknown', True, 0)):
                (root/name).write_text(json.dumps(dict(report_sha256=sha, review_completed=complete,
                                                       counts=dict(corrected_defect=corrected, corrected_normal=0, confirmed=40))))
                reviews.append(str(root/name))
            report = summarize(path, reviews)
            group = report['releases'][0]
            self.assertEqual(dict(reviewed_requests=2, requests_corrected=1, corrected_cells=2), group['human_review'])
            self.assertEqual((1, 1, 1), (report['unmatched_review_records'], report['incomplete_review_records'],
                                         group['requests_with_defect_warning']))
            (root/'bad.json').write_text('{"counts": {}}')
            with self.assertRaisesRegex(ValueError, 'not a listing review record'):
                summarize(path, [str(root/'bad.json')])

    def test_strict_log_and_cli_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for text, message in (('', 'no records'), ('not json\n', ''), (json.dumps(dict(kind='other', schema_version=1)) + '\n', 'schema-1')):
                (root/'bad.jsonl').write_text(text)
                with self.subTest(text=text[:10]), self.assertRaises(ValueError) as caught:
                    summarize(root/'bad.jsonl')
                self.assertIn(message, str(caught.exception))
            path = write(root, [entry(0, 0), entry(10, 1)])
            stdout = io.StringIO()
            with patch('sys.argv', ['card-condition', 'pilot-summary', str(path)]), redirect_stdout(stdout):
                main()
            self.assertEqual(['r1'], [g['release_id'] for g in json.loads(stdout.getvalue())['releases']])


if __name__ == '__main__':
    unittest.main()
