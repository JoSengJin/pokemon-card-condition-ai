import copy
import math
import unittest

from card_condition.evaluation_suite_inputs import checked_predictions
from card_condition.evaluation_suite_metrics import question_cells, subgroup_denominators
from card_condition.physical_uncertainty import QUESTIONS


def units(n=30):
    rows, metadata = [], {}
    for truth in (0, 1):
        for i in range(n):
            group = f'{truth}-{i}'
            metadata[group] = dict(side_annotations={s: dict(visibility_issues=[] if not truth else ['glare'])
                                                     for s in ('front', 'back')})
            for side in ('front', 'back'):
                rows.append(dict(id=group+'/'+side, card_id=group, group=group, side=side, box=[0, 0, 1, 1],
                    labels={q: truth for q in QUESTIONS}, probabilities={q: .9 if truth else .1 for q in QUESTIONS}))
    return rows, metadata


class SuiteInputsTest(unittest.TestCase):
    def test_projection_identity_truth_geometry_and_unit_count_are_exact(self):
        rows, _ = units(1)
        source = [{k: v for k, v in r.items() if k != 'probabilities'} for r in rows]
        report = dict(predictions=copy.deepcopy(rows))
        self.assertEqual(rows, checked_predictions(report, source, 'region_final', QUESTIONS))
        variants = []
        for key, value in (('labels', {q: True for q in QUESTIONS}), ('group', 'other'), ('box', [0, 0, .9, 1])):
            changed = copy.deepcopy(rows)
            changed[0][key] = value
            variants.append(changed)
        variants += [rows[:-1], rows + [rows[0]], [dict(rows[0], id='extra'), *rows[1:]]]
        for predictions in variants:
            with self.assertRaises(ValueError):
                checked_predictions(dict(predictions=predictions), source, 'region_final', QUESTIONS)

    def test_side_uses_source_group_and_side_and_rejects_bad_scores(self):
        rows, _ = units(1)
        source = [{k: v for k, v in r.items() if k != 'probabilities'} for r in rows]
        report = dict(predictions=[{k: r[k] for k in ('id', 'labels', 'probabilities')} for r in rows])
        result = checked_predictions(report, source, 'side_final', QUESTIONS)
        self.assertEqual(rows, result)
        for score in (True, math.nan, math.inf, -1., 1.01, '0.5'):
            changed = copy.deepcopy(report)
            changed['predictions'][0]['probabilities'][QUESTIONS[0]] = score
            with self.assertRaises(ValueError):
                checked_predictions(changed, source, 'side_final', QUESTIONS)
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            checked_predictions(report, source, 'side_final', ['edge_defect'])

    def test_fixed_raw_threshold_and_class_minima(self):
        rows, metadata = units()
        cells = question_cells(rows, QUESTIONS, QUESTIONS, metadata)
        self.assertEqual(10, len(cells))
        self.assertTrue(all(c['c_numeric_condition_met'] and c['d1_class_quantity_met'] for c in cells))
        self.assertTrue(all(c['positive_units'] == c['negative_units'] == 30 for c in cells))
        positives = [r for r in rows if r['side'] == 'front' and r['labels']['edge_defect'] == 1]
        positives[0]['probabilities']['edge_defect'] = .5
        self.assertEqual(0., question_cells(rows, QUESTIONS, ['edge_defect'], metadata)[0]['false_negative_rate'])
        for r in positives[:2]:
            r['probabilities']['edge_defect'] = .499
        front = question_cells(rows, QUESTIONS, ['edge_defect'], metadata)[0]
        self.assertAlmostEqual(2/30, front['false_negative_rate'])
        self.assertFalse(front['c_numeric_condition_met'])

    def test_missing_score_unknown_truth_and_unsupported_never_pass(self):
        rows, metadata = units()
        positive = next(r for r in rows if r['labels']['edge_defect'] == 1)
        positive['probabilities']['edge_defect'] = None
        cell = question_cells(rows, QUESTIONS, ['edge_defect'], metadata)[0]
        self.assertEqual(30, cell['positive_units'])
        self.assertEqual(1, cell['unavailable_positive_scores'])
        self.assertIsNone(cell['false_negative_rate'])
        self.assertFalse(cell['c_numeric_condition_met'])
        rows[0]['labels']['edge_defect'] = None
        cell = question_cells(rows, QUESTIONS, ['edge_defect'], metadata)[0]
        self.assertEqual(29, cell['negative_units'])
        self.assertEqual(1, cell['unknown_truth_units'])
        self.assertFalse(question_cells([], [], ['edge_defect'], {})[0]['c_numeric_condition_met'])
        self.assertFalse(question_cells(rows, [], ['edge_defect'], metadata)[0]['supported'])

    def test_subgroups_disclose_unknowns_and_count_cards_without_patch_inflation(self):
        rows, metadata = units(1)
        metadata['1-0']['language'] = 'ja'
        metadata['1-0']['edition'] = 'declared edition'
        groups = subgroup_denominators(rows * 3, metadata, 'edge_defect', 'front')
        lookup = {(g['dimension'], g['value']): g for g in groups}
        self.assertEqual(1, lookup['language', 'unknown']['physical_cards'])
        self.assertEqual(3, lookup['language', 'unknown']['units'])
        self.assertEqual(1, lookup['language', 'ja']['positive_physical_cards'])
        self.assertEqual(1, lookup['capture_issues', 'glare']['physical_cards'])
        metadata['1-0']['language'] = ['guessed']
        with self.assertRaises(ValueError):
            subgroup_denominators(rows, metadata, 'edge_defect', 'front')
