from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from card_condition.cli import main
from card_condition.listing_model import ListingAnalyzer
from card_condition.listing_review import review_page, review_record
from test_release import fixture_release


def analyzed(root):
    """Pinned synthetic release run with a reviewed front and a missing back photo."""
    manifest, _ = fixture_release(root)
    request_path = root/'request.json'
    report = ListingAnalyzer(release=manifest, device='cpu').analyze(json.loads(request_path.read_text()))
    (root/'report.json').write_text(json.dumps(report))
    return root/'report.json', request_path, report


def decisions_for(page, value):
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page).group(1))
    return dict(report_sha256=data['report_sha256'], id=data['id'],
                decisions=[dict(side=s, area=a, label=l, decision=value) for s, a, l in data['cells']])


class ListingReviewTest(unittest.TestCase):
    def test_page_shows_photo_regions_release_verdicts_and_hold_reasons(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_path, request_path, report = analyzed(root)
            summary = review_page(report_path, request_path, root/'page.html')
            page = (root/'page.html').read_text()
            cells = report['listing_readiness']['records'][0]['cells']
            self.assertEqual(len(cells), summary['cells'])
            self.assertEqual(len(cells), page.count("<tr data-key="))
            self.assertIn('릴리스 fixture-0', page)
            self.assertIn(report['model_sha256'], page)
            self.assertIn('data:image/jpeg;base64,', page)
            self.assertEqual(9, page.count('class="cell'))
            self.assertIn('사진 없음', page)
            self.assertIn('missing_photo', page)
            self.assertIn('centering_not_evaluated', page)
            self.assertEqual(report['release'], summary['release'])

    def test_changed_photo_or_other_listing_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_path, request_path, _ = analyzed(root)
            Image.new('RGB', (96, 128), (1, 2, 3)).save(root/'photo.png')
            with self.assertRaisesRegex(ValueError, 'differs from the analyzed photo'):
                review_page(report_path, request_path, root/'page.html')
            request_path.write_text(json.dumps(dict(id='other')))
            with self.assertRaisesRegex(ValueError, 'same single listing'):
                review_page(report_path, request_path, root/'page.html')
            self.assertFalse((root/'page.html').exists())

    def test_record_requires_exact_result_and_every_cell(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_path, request_path, _ = analyzed(root)
            review_page(report_path, request_path, root/'page.html')
            page = (root/'page.html').read_text()
            complete = decisions_for(page, 'confirmed')
            complete['decisions'][0]['decision'] = 'corrected_defect'
            (root/'done.json').write_text(json.dumps(complete))
            result = review_record(report_path, root/'done.json', root/'record.json')
            self.assertTrue(result['review_completed'])
            self.assertFalse(result['ground_truth'])
            self.assertEqual(1, result['counts']['corrected_defect'])
            saved = json.loads((root/'record.json').read_text())
            self.assertFalse(saved['used_for_training'] or saved['changes_model_verdict'])
            with self.assertRaisesRegex(ValueError, 'exists'):
                review_record(report_path, root/'done.json', root/'record.json')
            partial = decisions_for(page, '')
            (root/'partial.json').write_text(json.dumps(partial))
            result = review_record(report_path, root/'partial.json', root/'partial-record.json')
            self.assertFalse(result['review_completed'])
            self.assertEqual(result['cells'], result['unreviewed'])
            for change in (dict(report_sha256='0'*64), dict(decisions=complete['decisions'][1:]),
                           dict(decisions=[dict(d, decision='normal') for d in complete['decisions']])):
                (root/'bad.json').write_text(json.dumps(dict(complete, **change)))
                with self.subTest(change=list(change)), self.assertRaises(ValueError):
                    review_record(report_path, root/'bad.json', root/'bad-record.json')
            self.assertFalse((root/'bad-record.json').exists())

    def test_cli_builds_review_page(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_path, request_path, _ = analyzed(root)
            stdout = io.StringIO()
            with patch('sys.argv', ['card-condition', 'listing-review', str(report_path), str(request_path),
                                    '--output', str(root/'cli.html')]), redirect_stdout(stdout):
                main()
            self.assertEqual('fixture-0', json.loads(stdout.getvalue())['release']['release_id'])
            self.assertTrue((root/'cli.html').is_file())


if __name__ == '__main__':
    unittest.main()
