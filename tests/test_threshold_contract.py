"""Hand-calculated contracts for threshold sweeps and equal-card weighting."""
import copy
import unittest
from card_condition.region_thresholds import group_error_rates, region_threshold_analysis

KEY = 'edge_defect'


def prediction(group, side, truth, score, key=KEY):
    return {'group': group, 'side': side, 'labels': {key: truth}, 'probabilities': {key: score}}


class ThresholdContractTest(unittest.TestCase):
    ROWS = [prediction('g1', 'front', 1, .9), prediction('g1', 'front', 0, .4), prediction('g2', 'back', 1, .35),
            prediction('g2', 'back', 0, .05), prediction('g3', 'back', None, .99)]

    def test_every_threshold_matches_the_hand_table(self):
        # threshold: (tp, fp, tn, fn). Row scores .9/1, .4/0, .35/1, .05/0; the unknown row is unscored.
        expected = {.1: (2, 1, 1, 0), .2: (2, 1, 1, 0), .3: (2, 1, 1, 0), .4: (1, 1, 1, 1), .5: (1, 0, 2, 1),
                    .6: (1, 0, 2, 1), .7: (1, 0, 2, 1), .8: (1, 0, 2, 1), .9: (1, 0, 2, 1)}
        sweep = region_threshold_analysis(self.ROWS, [KEY])
        self.assertEqual(list(expected), [s['threshold'] for s in sweep])
        for step in sweep:
            tp, fp, tn, fn = expected[step['threshold']]
            with self.subTest(threshold=step['threshold']):
                self.assertEqual(dict(tp=tp, tn=tn, fp=fp, fn=fn), step['metrics'][KEY])
                rates = step['rates'][KEY]
                self.assertEqual((tp / (tp + fp), tp / (tp + fn), fp / (fp + tn), fn / (tp + fn)),
                                 (rates['precision'], rates['recall'], rates['false_positive_rate'], rates['miss_rate']))
                # Classes never change with the threshold; only their split into correct and wrong does.
                self.assertEqual((2, 2), (tp + fn, fp + tn))

    def test_sides_cards_and_unknown_rows_at_one_threshold(self):
        step = region_threshold_analysis(self.ROWS, [KEY])[3]
        self.assertEqual(.4, step['threshold'])
        self.assertEqual((dict(tp=1, tn=0, fp=1, fn=0), dict(tp=0, tn=1, fp=0, fn=1)),
                         (step['by_side']['front'][KEY], step['by_side']['back'][KEY]))
        step = region_threshold_analysis(self.ROWS, [KEY])[4]
        # g1: no error either way; g2: its only defect is missed; g3 has only an unknown row and is counted nowhere.
        self.assertEqual({'negative_groups': 2, 'positive_groups': 2, 'mean_false_positive_rate': 0.,
                          'mean_miss_rate': .5}, step['group_error_rates'][KEY])

    def test_kinds_are_independent_and_input_is_not_modified(self):
        rows = [dict(prediction('g1', 'front', 1, .9), labels={KEY: 1, 'corner_defect': None},
                     probabilities={KEY: .9, 'corner_defect': .9}),
                dict(prediction('g1', 'front', 0, .1), labels={KEY: 0, 'corner_defect': None},
                     probabilities={KEY: .1, 'corner_defect': .9})]
        before = copy.deepcopy(rows)
        step = region_threshold_analysis(rows, [KEY, 'corner_defect'])[4]
        self.assertEqual(dict(tp=1, tn=1, fp=0, fn=0), step['metrics'][KEY])
        self.assertEqual(dict(tp=0, tn=0, fp=0, fn=0), step['metrics']['corner_defect'])
        self.assertTrue(all(value is None for value in step['rates']['corner_defect'].values()))
        self.assertEqual(before, rows)

    def test_equal_card_weight_differs_from_pooled_rate(self):
        # Card A: 1 wrong of 4 normals (.25). Card B: 1 wrong of 1 normal (1). Card C: 2 of 2 defects found.
        cells = {'A': {KEY: dict(fp=1, tn=3, fn=0, tp=0)}, 'B': {KEY: dict(fp=1, tn=0, fn=0, tp=0)},
                 'C': {KEY: dict(fp=0, tn=0, fn=0, tp=2)}, 'D': {KEY: dict(fp=0, tn=0, fn=0, tp=0)}}
        summary = group_error_rates(cells, [KEY])[KEY]
        self.assertEqual((2, 1, (.25 + 1) / 2, 0.), (summary['negative_groups'], summary['positive_groups'],
                         summary['mean_false_positive_rate'], summary['mean_miss_rate']))
        self.assertNotEqual(2 / 5, summary['mean_false_positive_rate'])


if __name__ == '__main__':
    unittest.main()
