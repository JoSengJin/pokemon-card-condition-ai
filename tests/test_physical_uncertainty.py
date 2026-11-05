import copy
import math
import unittest

from card_condition.physical_uncertainty import QUESTIONS, Z, physical_uncertainty, wilson_upper


def row(group, truth, score, side='front'):
    return dict(group=group, side=side, labels={q: truth for q in QUESTIONS},
                probabilities={q: score for q in QUESTIONS})


class PhysicalUncertaintyTest(unittest.TestCase):
    def test_wilson_known_values_and_invalid_counts(self):
        self.assertIsNone(wilson_upper(0, 0))
        self.assertAlmostEqual(Z * Z / (30 + Z * Z), wilson_upper(0, 30), places=14)
        self.assertAlmostEqual(1., wilson_upper(30, 30))
        self.assertGreater(wilson_upper(1, 30), .10)
        for args in ((-1, 30), (31, 30), (True, 30), (1, 2.5)):
            with self.assertRaises(ValueError):
                wilson_upper(*args)

    def test_all_questions_sides_minimum_and_no_certification(self):
        rows = [row(f'{truth}-{i}', truth, .9 if truth else .1, side)
                for truth in (0, 1) for i in range(30) for side in ('front', 'back')]
        report = physical_uncertainty(rows, QUESTIONS)
        self.assertTrue(report['all_numeric_conditions_met'])
        self.assertFalse(report['milestone_verified'])
        self.assertEqual(10, len(report['cells']))
        self.assertEqual(report, physical_uncertainty(rows * 8, QUESTIONS))
        for cell in report['cells']:
            self.assertEqual(30, cell['miss']['physical_cards'])
            self.assertEqual(30, cell['false_alarm']['physical_cards'])
        failed = copy.deepcopy(rows)
        failed[60]['probabilities']['edge_defect'] = .49
        self.assertFalse(physical_uncertainty(failed, QUESTIONS)['all_numeric_conditions_met'])
        self.assertFalse(physical_uncertainty(rows, ['edge_defect'])['all_numeric_conditions_met'])

    def test_any_error_per_card_and_separate_sides(self):
        rows = [row('a', 1, .9), row('a', 1, .1), row('a', 0, .9),
                row('b', 0, .1), row('b', 0, .9), row('a', 1, .9, 'back')]
        cells = physical_uncertainty(rows, ['edge_defect'])['cells']
        front, back = cells[:2]
        self.assertEqual((1, 1, 1.), (front['miss']['physical_cards'],
                         front['miss']['observed_events'], front['miss']['event_rate']))
        self.assertEqual((1, 1), (front['false_alarm']['physical_cards'], front['false_alarm']['observed_events']))
        self.assertEqual(0., back['miss']['event_rate'])
        self.assertIsNone(back['false_alarm']['upper_95'])
        self.assertEqual(physical_uncertainty(rows, ['edge_defect']),
                         physical_uncertainty(rows * 20, ['edge_defect']))

    def test_unknown_and_missing_scores_never_become_normal_or_pass(self):
        rows = [row('a', None, .1), row('a', 0, .1), row('b', 1, None), row('c', 0, None)]
        cell = physical_uncertainty(rows, QUESTIONS)['cells'][0]
        self.assertEqual(1, cell['unknown_truth_units'])
        self.assertEqual(1, cell['cards_with_unknown_truth'])
        for key in ('miss', 'false_alarm'):
            self.assertEqual(1, cell[key]['physical_cards'])
            self.assertEqual(1, cell[key]['unavailable_cards'])
            self.assertIsNone(cell[key]['upper_95'])
            self.assertIsNone(cell[key]['event_rate'])
            self.assertFalse(cell[key]['numeric_condition_met'])
        empty = physical_uncertainty([], QUESTIONS)
        self.assertFalse(empty['all_numeric_conditions_met'])
        self.assertTrue(all(c['miss']['physical_cards'] == 0 for c in empty['cells']))

    def test_invalid_inputs_rejected(self):
        valid = row('card', 1, .9)
        variants = [dict(valid, group=''), dict(valid, side='left'), dict(valid, labels=[]),
                    dict(valid, probabilities={})]
        for bad in (True, -1, '0', 2):
            variants.append(dict(valid, labels=dict(valid['labels'], edge_defect=bad)))
        for bad in (True, math.nan, math.inf, -.1, 1.1, '0.9'):
            variants.append(dict(valid, probabilities=dict(valid['probabilities'], edge_defect=bad)))
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                physical_uncertainty([variant], QUESTIONS)
