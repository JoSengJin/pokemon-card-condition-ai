import unittest

from card_condition.region_thresholds import region_threshold_analysis


class RegionThresholdTest(unittest.TestCase):
    def test_boundary_unknown_side_and_equal_group_weight(self):
        def prediction(group, side, truth, value):
            return {'group': group, 'side': side, 'labels': {'edge_defect': truth},
                    'probabilities': {'edge_defect': value}}
        rows = [prediction('many', 'front', 0, .5)] * 3 + [
            prediction('few', 'back', 0, .1), prediction('few', 'front', 1, .5),
            prediction('few', 'back', None, .99)]
        sweep = region_threshold_analysis(rows, ['edge_defect'])
        middle = sweep[4]
        self.assertEqual(.5, middle['threshold'])
        self.assertEqual(dict(tp=1, tn=1, fp=3, fn=0), middle['metrics']['edge_defect'])
        self.assertEqual(.25, middle['rates']['edge_defect']['precision'])
        self.assertEqual(.75, middle['rates']['edge_defect']['false_positive_rate'])
        self.assertEqual(.5, middle['group_error_rates']['edge_defect']['mean_false_positive_rate'])
        self.assertEqual(1, middle['by_side']['back']['edge_defect']['tn'])
        self.assertEqual(0, middle['by_side']['back']['edge_defect']['tp'])
        self.assertEqual(4, sweep[0]['metrics']['edge_defect']['fp'])
        self.assertEqual(1, sweep[-1]['metrics']['edge_defect']['fn'])
        self.assertIsNone(sweep[-1]['rates']['edge_defect']['precision'])
        self.assertEqual(sorted(s['metrics']['edge_defect']['fn'] for s in sweep),
                         [s['metrics']['edge_defect']['fn'] for s in sweep])
        self.assertEqual(5, sum(middle['metrics']['edge_defect'].values()))

    def test_absent_truth_has_no_zero_error_claim(self):
        rows = [{'group': 'a', 'side': 'back', 'labels': {'surface_defect': None},
                 'probabilities': {'surface_defect': .8}}]
        result = region_threshold_analysis(rows, ['surface_defect'])[4]
        self.assertTrue(all(value is None for value in result['rates']['surface_defect'].values()))
        self.assertEqual(0, result['group_error_rates']['surface_defect']['negative_groups'])
        self.assertIsNone(result['group_error_rates']['surface_defect']['mean_miss_rate'])
