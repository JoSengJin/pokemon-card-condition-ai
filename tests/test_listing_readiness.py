import copy
import unittest

from card_condition.data import LABELS
from card_condition.listing_readiness import listing_readiness
from card_condition.regions import GLARE_AREAS, REGION_LABELS, VISIBILITY_ISSUES


def example():
    row = dict(id='a', group='physical-a', front='front.png', back='back.png',
               side_annotations={})
    for side in ('front', 'back'):
        row['side_annotations'][side] = dict(image=row[side], box=[0, 0, 1, 1],
            labels={k: None for k in LABELS}, visibility_issues=[])
    predictions = [dict(card_id='a', side=side, area=area,
        probabilities={k: .1 for k in REGION_LABELS})
        for side in ('front', 'back') for area in GLARE_AREAS]
    return row, predictions


class ListingReadinessTest(unittest.TestCase):
    def test_partial_glare_keeps_observed_defects_and_normals(self):
        row, predictions = example()
        row['side_annotations']['back'].update(visibility_issues=['glare'], glare_areas=['lower_right'])
        predictions[0]['probabilities']['surface_defect'] = .9
        before = copy.deepcopy((row, predictions))
        result = listing_readiness([row], predictions, list(REGION_LABELS))
        record = result['records'][0]
        self.assertTrue(record['additional_photos_required'])
        self.assertEqual(['additional_photos_required', 'gemini_review'], record['actions'])
        surface = {(c['side'], c['area']): c for c in record['cells'] if c['label'] == 'surface_defect'}
        self.assertEqual('unknown', surface['back', 'lower_right']['state'])
        self.assertIsNone(surface['back', 'lower_right']['score'])
        self.assertEqual('normal', surface['back', 'center']['state'])
        self.assertEqual('defect', surface['front', 'upper_left']['state'])
        self.assertEqual(before, (row, predictions))

    def test_complete_regions_do_not_claim_whole_listing_complete(self):
        row, predictions = example()
        result = listing_readiness([row], predictions, list(REGION_LABELS))
        record = result['records'][0]
        self.assertEqual(42, record['required_region_cells'])
        self.assertEqual(42, record['accepted_region_cells'])
        self.assertTrue(record['region_scope_complete'])
        self.assertFalse(record['local_complete_candidate'])
        self.assertEqual(0, result['local_completion_rate'])
        self.assertIn('centering_not_evaluated', record['whole_listing_blockers'])

    def test_missing_photo_sparse_predictions_and_unsupported(self):
        row, predictions = example()
        row['back'] = None
        del row['side_annotations']['back']
        other = dict(id='b', group='physical-a', front='other.png', back=None)
        result = listing_readiness([row, other], predictions[:1], ['edge_defect'])
        self.assertEqual((2, 1), (result['listings'], result['physical_groups']))
        self.assertEqual(2, result['additional_photos_required'])
        reasons = {c['reason'] for c in result['records'][0]['cells']}
        self.assertTrue({'missing_photo', 'unsupported', 'not_evaluated'} <= reasons)
        predictions[0]['probabilities']['edge_defect'] = .5
        result = listing_readiness([row], predictions[:1], ['edge_defect'])
        self.assertIn('score_deferred', {c['reason'] for c in result['records'][0]['cells']})
        row['side_annotations']['front'].update(visibility_issues=['glare'])
        result = listing_readiness([row], predictions, list(REGION_LABELS))
        self.assertEqual(0, result['records'][0]['accepted_region_cells'])

    def test_observation_limits_override_both_confident_outputs(self):
        for issue in VISIBILITY_ISSUES:
            for score in (.001, .999):
                with self.subTest(issue=issue, score=score):
                    row, predictions = example()
                    row['side_annotations']['back']['visibility_issues'] = [issue]
                    for prediction in predictions:
                        prediction['probabilities'] = {k: score for k in REGION_LABELS}
                    before = copy.deepcopy((row, predictions))
                    result = listing_readiness([row], predictions, list(REGION_LABELS))
                    record = result['records'][0]
                    back = [c for c in record['cells'] if c['side'] == 'back']
                    front = [c for c in record['cells'] if c['side'] == 'front']
                    self.assertEqual(21, len(back))
                    self.assertTrue(all(c['state'] == 'unknown' and c['score'] is None
                                        and c['reason'] == 'observation_limited' for c in back))
                    self.assertTrue(all(c['state'] == ('normal' if score < .3 else 'defect')
                                        for c in front))
                    self.assertTrue(record['additional_photos_required'])
                    self.assertFalse(record['local_complete_candidate'])
                    self.assertEqual(0, result['actual_calls_saved'])
                    self.assertEqual(before, (row, predictions))

    def test_missing_observation_review_is_not_a_clear_face(self):
        row,predictions=example()
        del row['side_annotations']['front']['visibility_issues']
        before=copy.deepcopy((row,predictions))
        result=listing_readiness([row],predictions,list(REGION_LABELS))
        cells=result['records'][0]['cells']
        front=[c for c in cells if c['side']=='front']
        self.assertTrue(all(c['state']=='unknown' and c['score'] is None
                            and c['reason']=='observation_not_reviewed' for c in front))
        self.assertEqual(21,result['records'][0]['accepted_region_cells'])
        self.assertFalse(result['records'][0]['additional_photos_required'])
        self.assertTrue(result['records'][0]['region_model_review_required'])
        self.assertEqual(before,(row,predictions))
