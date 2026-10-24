import copy
import math
import unittest

from card_condition.visibility_compare import compare_reports, quality_summary
from card_condition.visibility_model import TARGET


def report(scores):
    rows = [dict(card_id=str(i),side='back',group=str(i),split='val',image=str(i),box=[0,0,1,1],
        image_hashes=[str(i)],visibility_issues=['glare'] if t else [],labels={TARGET:t},
        probabilities={TARGET:p}) for i,(t,p) in enumerate(scores)]
    return dict(target=TARGET,evaluation_kind='validation_observation_limit',predictions=rows,
                input_hashes={str(i):str(i) for i in range(len(rows))})


class VisibilityCompareTest(unittest.TestCase):
    def test_uniform_shift_is_not_ranking_gain(self):
        baseline = report([(0,.3),(0,.45),(1,.48),(1,.6)])
        candidate = report([(0,.4),(0,.55),(1,.58),(1,.7)])
        result = compare_reports(baseline,candidate)
        self.assertEqual(4,result['increased'])
        self.assertAlmostEqual(.1,result['mean_delta'])
        self.assertEqual(0,result['reference']['metrics_at_05']['fp'])
        self.assertEqual(1,result['candidate']['metrics_at_05']['fp'])
        self.assertEqual(1,result['reference']['metrics_at_05']['fn'])
        self.assertEqual(0,result['candidate']['metrics_at_05']['fn'])
        delta=result['rate_comparison_at_05']['change_percentage_points']
        self.assertEqual(-50,delta['false_negative_rate'])
        self.assertEqual(50,delta['false_positive_rate'])
        self.assertEqual(0,delta['accuracy'])
        self.assertFalse(result['rate_comparison_at_05']['errors_jointly_improved'])
        self.assertFalse(result['ranking_improved'])
        self.assertFalse(result['research_candidate_only'])
        self.assertFalse(result['production_ready'])
        tied = report([(0,.5),(0,.5),(1,.5),(1,.5)])
        quality = quality_summary(tied)
        self.assertAlmostEqual(math.log(2),quality['balanced_bce'])
        self.assertEqual(.5,quality['auroc'])
        self.assertFalse(quality['beats_null_baseline'])
        self.assertEqual(0,compare_reports(baseline,tied)['candidate_tp_at_budget'])

    def test_changed_inputs_refuse_comparison(self):
        source = report([(0,.3),(1,.6)])
        for field,value in [('group','other'),('box',[0,0,.5,.5]),('labels',{TARGET:1}),
                            ('visibility_issues',['glare']),('image_hashes',['other'])]:
            changed = copy.deepcopy(source)
            changed['predictions'][0][field] = value
            with self.assertRaisesRegex(ValueError,'differ'):
                compare_reports(source,changed)
        changed = copy.deepcopy(source)
        changed['input_hashes']['0'] = 'different'
        with self.assertRaisesRegex(ValueError,'differ'):
            compare_reports(source,changed)
        changed = copy.deepcopy(source)
        changed['predictions'][0]['probabilities'][TARGET] = float('nan')
        with self.assertRaisesRegex(ValueError,'Invalid'):
            compare_reports(source,changed)
