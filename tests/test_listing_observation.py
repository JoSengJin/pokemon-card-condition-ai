import unittest
from unittest.mock import patch

from card_condition.listing_observation import observation_evidence


class ListingObservationTest(unittest.TestCase):
    def test_missing_region_is_unknown_and_omitted_human_truth_stays_unknown(self):
        row=dict(id='card',group='physical',front='front.png',back='back.png',
            side_annotations=dict(front=dict(box=[0,0,1,1]),back=dict(box=None)))
        with patch('card_condition.listing_observation.VisibilityAnalyzer') as model:
            model.return_value.model_sha256='frozen'
            model.return_value.analyze.return_value=dict(observation_limit_score=.9)
            result=observation_evidence([row],'model.pt','cpu')
            model.return_value.analyze.assert_called_once_with('front.png',[0,0,1,1],side='front')
        self.assertIsNone(result['records'][0]['human_visibility_issues'])
        self.assertEqual('missing_card_region',result['records'][1]['reason'])
        self.assertIsNone(result['records'][1]['observation_limit_score'])
        self.assertTrue(result['requires_gemini'])
        self.assertFalse(result['human_annotations_changed'])

    def test_invalid_scores_fail_without_inventing_a_decision(self):
        row=dict(id='card',group='physical',front='front.png',
            side_annotations=dict(front=dict(box=[0,0,1,1])))
        for score in (float('nan'),float('inf'),-.1,1.1):
            with self.subTest(score=score), patch('card_condition.listing_observation.VisibilityAnalyzer') as model:
                model.return_value.analyze.return_value=dict(observation_limit_score=score)
                with self.assertRaisesRegex(ValueError,'Invalid observation score'):
                    observation_evidence([row],'model.pt','cpu')
