import unittest
from card_condition.evaluation_suite_inputs import checked_predictions
from card_condition.evaluation_suite_metrics import question_cells
from test_frozen_judgment_identity import judgment,LABELS


class UnsupportedTruthIdentityTest(unittest.TestCase):
    def test_known_unsupported_alias_is_rejected_for_matching_or_conflicting_truth(self):
        for truth in (0,1):
            rows=[judgment(),judgment('alias')]
            rows[1]['labels']['edge_defect']=truth
            predictions=[dict(r,probabilities={q:None for q in LABELS}) for r in rows]
            with self.subTest(truth=truth),self.assertRaisesRegex(ValueError,'Duplicate labeled photo'):
                checked_predictions(dict(predictions=predictions),rows,'region_final',['corner_defect'])

    def test_supplied_source_photo_identity_cannot_be_overridden_by_row_metadata(self):
        rows=[judgment(),judgment('alias')]
        rows[1]['image_sha256']='b'*64
        predictions=[dict(r,probabilities={q:None for q in LABELS}) for r in rows]
        photos={r['card_id']:{'front':'c'*64} for r in rows}
        with self.assertRaisesRegex(ValueError,'Duplicate labeled photo'):
            checked_predictions(dict(predictions=predictions),rows,'region_final',['corner_defect'],photo_sha256=photos)

    def test_unknown_alias_remains_unknown_and_does_not_add_known_quantity(self):
        rows=[judgment(),judgment('unknown')]
        rows[1]['labels']={q:None for q in LABELS}
        predictions=[dict(r,probabilities={q:None for q in LABELS}) for r in rows]
        normalized=checked_predictions(dict(predictions=predictions),rows,'region_final',['corner_defect'])
        cell=question_cells(normalized,['corner_defect'],['edge_defect'],{r['card_id']:{} for r in rows})[0]
        self.assertEqual(1,cell['positive_units'])
        self.assertEqual(1,cell['unknown_truth_units'])
        self.assertEqual(1,cell['unavailable_positive_scores'])
        self.assertIsNone(cell['false_negative_rate'])

    def test_distinct_source_photos_areas_or_questions_remain_distinct(self):
        for field,value in [('image_sha256','b'*64),('area','upper_center'),('labels',dict(edge_defect=None,corner_defect=None,surface_defect=1))]:
            rows=[judgment(),judgment('different')];rows[1][field]=value
            predictions=[dict(r,probabilities={q:None for q in LABELS}) for r in rows]
            with self.subTest(field=field):
                self.assertEqual(2,len(checked_predictions(dict(predictions=predictions),rows,'region_final',['corner_defect'])))

    def test_scores_outside_model_support_are_still_rejected(self):
        rows=[judgment()]
        predictions=[dict(rows[0],probabilities=dict(edge_defect=.9,corner_defect=None,surface_defect=None))]
        with self.assertRaisesRegex(ValueError,'unsupported raw prediction'):
            checked_predictions(dict(predictions=predictions),rows,'region_final',['corner_defect'])
