from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from card_condition.cli import main
from card_condition.data import LABELS
from card_condition.listing_readiness import listing_readiness
from card_condition.listing_review import review_page, review_record, whole_face_cells


def manual_fixture(root, back=True, front_box=True, ident='scope-fixture'):
    request = dict(id=ident)
    row = dict(id=ident, group=ident, front=None, back=None, side_annotations={})
    hashes = {}
    for side in ('front', 'back'):
        if side == 'back' and not back:
            continue
        path = root / (side + '.png')
        Image.new('RGB', (120, 180), (40, 80 if side == 'front' else 120, 180)).save(path)
        box = [.1, .1, .9, .9] if side != 'front' or front_box else None
        request[side] = dict(image=str(path), box=box, visibility_issues=[])
        row[side] = str(path)
        row['side_annotations'][side] = dict(image=str(path), box=box, visibility_issues=[], labels={q: None for q in LABELS})
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(id=ident, model_sha256='a'*64, input_photo_sha256=hashes,
                  listing_readiness=listing_readiness([row], [], []), release=None)
    report_path, request_path = root/'report.json', root/'request.json'
    report_path.write_text(json.dumps(report))
    request_path.write_text(json.dumps(request))
    decisions = dict(id=ident, report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
        decisions=[dict(side=c['side'], area=c['area'], label=c['label'], decision='confirmed')
                   for c in report['listing_readiness']['records'][0]['cells']],
        face_decisions=[dict(side=side, area='face', label=label,
                            decision='undecidable' if side == 'back' and not back or side == 'front' and not front_box else
                                     'confirmed' if label == 'centering_defect' else 'confirmed_observable')
                        for side in ('front', 'back') for label in ('centering_defect', 'observation_limited')])
    return report_path, request_path, report, decisions


class WholeScopeReviewTest(unittest.TestCase):
    def test_page_has_four_manual_questions_without_changing_42_model_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_path, request_path, report, decisions = manual_fixture(root)
            before = report_path.read_bytes()
            summary = review_page(report_path, request_path, root/'page.html')
            page = (root/'page.html').read_text()
            self.assertEqual(42, summary['cells'])
            self.assertEqual(4, summary['manual_face_cells'])
            self.assertEqual(42, page.count('<tr data-key='))
            self.assertEqual(4, page.count('<tr data-face-key='))
            for row in re.findall(r'<tr data-face-key=[^>]+>(.*?)</tr>', page):
                if '관찰 제한' in row:
                    self.assertIn('confirmed_observable', row)
                    self.assertNotIn('corrected_normal', row)
                    self.assertNotIn('corrected_defect', row)
            self.assertIn('관찰 제한은 카드 손상을 뜻하지 않는다', page)
            self.assertTrue(all(c['score'] is None and c['state'] == 'unknown' for c in whole_face_cells(report)))
            self.assertEqual(before, report_path.read_bytes())

    def test_legacy_region_completion_and_new_full_scope_completion_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_path, request_path, report, decisions = manual_fixture(root)
            legacy = copy.deepcopy(decisions);legacy.pop('face_decisions')
            source = root/'decisions.json';source.write_text(json.dumps(legacy))
            old = review_record(report_path, source, root/'legacy.json')
            self.assertTrue(old['review_completed'] and old['region_review_completed'])
            self.assertFalse(old['face_review_completed'] or old['full_scope_review_completed'])
            source.write_text(json.dumps(decisions))
            result = review_record(report_path, source, root/'complete.json')
            self.assertTrue(result['full_scope_review_completed'])
            self.assertEqual(old['counts'], result['counts'])
            saved = json.loads((root/'complete.json').read_text())
            self.assertEqual(2, saved['face_counts']['observation_limited']['confirmed_observable'])
            self.assertFalse(saved['ground_truth'] or saved['used_for_training'] or saved['changes_model_verdict'])
            self.assertFalse(saved['face_decisions_are_model_predictions'])
            decisions['face_decisions'][0]['decision'] = ''
            source.write_text(json.dumps(decisions))
            partial = review_record(report_path, source, root/'partial.json')
            self.assertTrue(partial['region_review_completed'])
            self.assertFalse(partial['full_scope_review_completed'])
            self.assertEqual(1, partial['face_unreviewed'])

    def test_duplicate_missing_wrong_kind_or_bad_face_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_path, request_path, report, decisions = manual_fixture(root)
            variants = [None, [], decisions['face_decisions'][:-1],
                        [decisions['face_decisions'][0]]*4, [None]*4]
            wrong = copy.deepcopy(decisions['face_decisions']);wrong[1]['decision'] = 'corrected_normal';variants.append(wrong)
            for value in variants:
                source = root/'decisions.json';source.write_text(json.dumps(dict(decisions, face_decisions=value)))
                with self.assertRaises(ValueError):
                    review_record(report_path, source, root/'bad.json')
                self.assertFalse((root/'bad.json').exists())

    def test_missing_photo_or_card_box_cannot_be_reviewed_as_normal_or_observable(self):
        for back, front_box, side in ((False, True, 'back'), (True, False, 'front')):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                report_path, request_path, report, decisions = manual_fixture(root, back=back, front_box=front_box)
                cells = [c for c in whole_face_cells(report) if c['side'] == side]
                self.assertTrue(all(c['options'] == ['undecidable'] for c in cells))
                source = root/'decisions.json';source.write_text(json.dumps(decisions))
                self.assertTrue(review_record(report_path, source, root/'reviewed.json')['full_scope_review_completed'])
                for decision in decisions['face_decisions']:
                    if decision['side'] == side:
                        decision['decision'] = 'corrected_normal' if decision['label'] == 'centering_defect' else 'confirmed_observable'
                source.write_text(json.dumps(decisions))
                with self.assertRaisesRegex(ValueError, 'contradicts'):
                    review_record(report_path, source, root/'bad.json')

    def test_payload_escaping_and_face_keys_keep_exact_report_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            ident = '</script><script>alert(1)</script>'
            report_path, request_path, report, decisions = manual_fixture(root, ident=ident)
            review_page(report_path, request_path, root/'page.html')
            page = (root/'page.html').read_text()
            payload = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page).group(1))
            self.assertEqual(ident, payload['id'])
            self.assertEqual(42, len(payload['cells']))
            self.assertEqual(4, len(payload['face_cells']))
            self.assertNotIn('</script><script>alert(1)', page)
            self.assertIn('&lt;script&gt;alert(1)', page)
            wrong = dict(decisions, report_sha256='0'*64)
            source = root/'wrong.json';source.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'different result'):
                review_record(report_path, source, root/'bad.json')

    def test_cli_record_reports_full_scope_without_converting_it_to_ground_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_path, request_path, report, decisions = manual_fixture(root)
            source = root/'decisions.json';source.write_text(json.dumps(decisions))
            argv = ['card-condition', 'listing-review-record', str(report_path), str(source), '--output', str(root/'record.json')]
            with patch('sys.argv', argv), redirect_stdout(io.StringIO()) as output:
                main()
            result = json.loads(output.getvalue())
            self.assertTrue(result['full_scope_review_completed'])
            self.assertFalse(result['ground_truth'])
