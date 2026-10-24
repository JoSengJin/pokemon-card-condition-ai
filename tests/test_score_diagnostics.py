import unittest

from card_condition.score_diagnostics import score_diagnostics


def prediction(truth, score, group='a'):
    return dict(labels={'edge_defect': truth}, probabilities={'edge_defect': score}, group=group)


class ScoreDiagnosticsTest(unittest.TestCase):
    def test_exact_ranking_ties_and_no_coverage(self):
        rows = [prediction(1, .8), prediction(0, .8), prediction(1, .9),
                prediction(0, .2), prediction(None, .99)]
        r = score_diagnostics(rows, ['edge_defect'])['edge_defect']
        self.assertEqual(.875, r['auroc'])
        self.assertAlmostEqual(5/6, r['average_precision'])
        self.assertEqual(1, r['unknown'])
        self.assertEqual({'positive':2,'negative':2,'scored':4,'false_negative_rate':0.,
            'false_positive_rate':.5,'accuracy':.75},r['rates_at_05'])
        self.assertEqual(2, r['all_positive_baseline']['fp'])
        self.assertEqual(1, r['abstention_trials'][0]['accepted'])
        self.assertEqual(.25, r['abstention_trials'][0]['coverage_known'])
        self.assertEqual(0, r['abstention_trials'][0]['risk_known'])
        tied = score_diagnostics([prediction(0, .5), prediction(1, .5)], ['edge_defect'])['edge_defect']
        self.assertEqual(.5, tied['auroc'])
        self.assertEqual(.5, tied['average_precision'])
        self.assertIsNone(tied['abstention_trials'][0]['risk_known'])
        self.assertEqual(2, tied['abstention_trials'][-1]['accepted'])

    def test_group_weight_and_absent_classes(self):
        rows = [prediction(0, .9, 'many')]*3+[prediction(0, .1, 'few')]
        r = score_diagnostics(rows, ['edge_defect'])['edge_defect']
        self.assertIsNone(r['auroc'])
        self.assertIsNone(r['average_precision'])
        self.assertEqual(.75, r['abstention_trials'][1]['risk_known'])
        self.assertEqual(.5, r['abstention_trials'][1]['mean_group_risk'])
        r = score_diagnostics([prediction(None, .8)], ['edge_defect'])['edge_defect']
        self.assertIsNone(r['abstention_trials'][0]['coverage_known'])

    def test_constant_predictions_do_not_make_zero_misses_success(self):
        rows = [prediction(0,.8), prediction(0,.9), prediction(1,.95), prediction(None,.1)]
        r = score_diagnostics(rows,['edge_defect'])['edge_defect']
        self.assertEqual('all_known_predicted_defect',r['warning_at_05'])
        self.assertEqual({'normal':0,'defect':3},r['prediction_distribution_at_05'])
        self.assertEqual(.5,r['balanced_accuracy_at_05'])
        self.assertEqual(1.0,r['auroc'])
        r = score_diagnostics([prediction(0,.1),prediction(1,.2)],['edge_defect'])['edge_defect']
        self.assertEqual('all_known_predicted_normal',r['warning_at_05'])
        self.assertEqual(.5,r['balanced_accuracy_at_05'])
        r = score_diagnostics([prediction(0,.1),prediction(1,.9)],['edge_defect'])['edge_defect']
        self.assertIsNone(r['warning_at_05'])
        self.assertEqual(1.0,r['balanced_accuracy_at_05'])
        r = score_diagnostics([prediction(None,.9)],['edge_defect'])['edge_defect']
        self.assertEqual('both_truth_classes_required',r['warning_at_05'])
        self.assertIsNone(r['balanced_accuracy_at_05'])
        self.assertIsNone(r['rates_at_05']['accuracy'])

    def test_group_abstention_preserves_deferred_and_unknown_denominators(self):
        rows = [prediction(0,.29,'a'), prediction(1,.7,'a'), prediction(1,.1,'a'),
                prediction(0,.9,'a'), prediction(1,.3,'b'), prediction(0,.699,'b'),
                prediction(None,.99,'c')]
        r = score_diagnostics(rows,['edge_defect'])['edge_defect']
        trial = r['abstention_trials'][2]
        a,b,c = (trial['by_group'][g] for g in ('a','b','c'))
        self.assertEqual((1,1,1,1),tuple(a[k] for k in ('tp','tn','fp','fn')))
        self.assertEqual(.5,a['risk_known'])
        self.assertEqual((2,2,0),(b['known'],b['deferred_known'],b['accepted']))
        self.assertEqual(0,b['coverage_known'])
        self.assertIsNone(b['risk_known'])
        self.assertEqual((0,1),(c['known'],c['unknown']))
        self.assertIsNone(c['coverage_known'])
        self.assertIsNone(c['risk_known'])
        self.assertEqual(1,trial['zero_accepted_known_groups'])
        for trial in r['abstention_trials']:
            grouped = trial['by_group'].values()
            self.assertEqual(trial['accepted'],sum(g['accepted'] for g in grouped))
            self.assertEqual(trial['deferred_known'],sum(g['deferred_known'] for g in grouped))
            self.assertEqual(trial['errors'],sum(g['fp']+g['fn'] for g in grouped))
        self.assertEqual(0,r['abstention_trials'][-1]['zero_accepted_known_groups'])
