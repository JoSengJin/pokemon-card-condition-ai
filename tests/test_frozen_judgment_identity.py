import json
from pathlib import Path
import tempfile
import unittest

from card_condition.evaluation_suite_inputs import checked_predictions
from card_condition.evaluation_suite_metrics import confusion_counts
from card_condition.frozen_test import seal_test

LABELS = ['edge_defect', 'corner_defect', 'surface_defect']


def judgment(ident='one'):
    return dict(id=ident, card_id=ident, group='same-card', side='front', area='upper_left',
                image_sha256='a'*64, box=[0, 0, 1, 1], card_box=[0, 0, 1, 1],
                labels=dict(edge_defect=1, corner_defect=None, surface_defect=None))


class FrozenJudgmentIdentityTest(unittest.TestCase):
    def test_known_unit_aliases_are_rejected_even_with_a_different_box(self):
        for box in ([0, 0, 1, 1], [.1, .1, .9, .9]):
            rows = [judgment(), judgment('alias')]
            rows[1]['box'] = box
            rows[1]['card_box'] = box
            predictions = [dict(r, probabilities={q: .9 for q in LABELS}) for r in rows]
            with self.assertRaisesRegex(ValueError, 'Duplicate labeled photo'):
                checked_predictions(dict(predictions=predictions), rows, 'region_final', LABELS)

    def test_different_photos_regions_and_questions_remain_distinct(self):
        for field, value in (('image_sha256', 'b'*64), ('area', 'upper_center'),
                             ('labels', dict(edge_defect=None, corner_defect=1, surface_defect=None))):
            rows = [judgment(), judgment('another')]
            rows[1][field] = value
            predictions = [dict(r, probabilities={q: .9 for q in LABELS}) for r in rows]
            normalized = checked_predictions(dict(predictions=predictions), rows, 'region_final', LABELS)
            self.assertEqual(2, len(normalized))
            self.assertEqual(2, sum(sum(v.values()) for v in confusion_counts(normalized, LABELS).values()))

    def test_unknown_alias_is_not_normal_or_a_second_positive(self):
        rows = [judgment(), judgment('unknown-alias')]
        rows[1]['labels'] = {q: None for q in LABELS}
        predictions = [dict(r, probabilities={q: .9 for q in LABELS}) for r in rows]
        normalized = checked_predictions(dict(predictions=predictions), rows, 'region_final', LABELS)
        self.assertEqual(2, len(normalized))
        self.assertEqual(dict(tp=1, tn=0, fp=0, fn=0), confusion_counts(normalized, LABELS)['edge_defect'])

    def test_same_decoded_photo_cannot_be_front_and_back(self):
        rows = [judgment(), judgment('back-alias')]
        rows[1]['side'] = 'back'
        predictions = [dict(r, probabilities={q: .9 for q in LABELS}) for r in rows]
        with self.assertRaisesRegex(ValueError, 'both front and back'):
            checked_predictions(dict(predictions=predictions), rows, 'region_final', LABELS)

    def test_real_sealer_rejects_same_pixels_assigned_to_both_sides(self):
        from test_evaluation_inputs import evaluation_fixture
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, records, analyzer = evaluation_fixture(root, 'region')
            rows = [json.loads(line) for line in manifest.read_text().splitlines()]
            rows[0]['back'] = rows[0]['front']
            rows[0]['side_annotations']['back']['image'] = rows[0]['front']
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            with self.assertRaisesRegex(ValueError, 'both front and back'):
                seal_test(manifest, [history], root/'seal.json')
            self.assertFalse((root/'seal.json').exists())
            self.assertEqual(before, manifest.read_bytes())

    def test_assessment_rejects_real_alias_projection_without_rewriting_truth(self):
        from test_evaluation_suite import saved_suite
        from card_condition.evaluation_suite import assess_suite
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2, alias=True)
            before = args[0].read_bytes()
            with self.assertRaisesRegex(ValueError, 'Duplicate labeled photo'):
                assess_suite(*args, reports, root/'assessment.json')
            self.assertFalse((root/'assessment.json').exists())
            self.assertEqual(before, args[0].read_bytes())
            self.assertEqual(3, len(list((root/'ledger').glob('*.json'))))
