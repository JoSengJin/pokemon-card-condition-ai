import ast
import math
from pathlib import Path
import unittest

from card_condition.rank_budget import card_operating_points, card_scores, rank_budget_report

REL = (0.234, 0.688)
ROOT = Path(__file__).resolve().parents[1]


def run(scores, ids=None, groups=None, k=0.5, **kw):
    ids = ids or [f'z{i}' for i in range(len(scores))]
    return rank_budget_report(scores, ids, groups or [f'g{i}' for i in range(len(scores))], k, label_reliability_interval=REL, **kw)


class RankBudgetTest(unittest.TestCase):
    def test_fixed_fields_and_top_k(self):
        r = run([.1, .9, .5, .7])
        self.assertIs(r['development_evaluation'], True)
        self.assertIs(r['independent_validation'], False)
        self.assertEqual(r['label_reliability_interval'], list(REL))
        self.assertEqual([x['id'] for x in r['inspect']], ['z1', 'z3'])

    def test_ties_ignore_input_order(self):
        a = run([.5, .5, .5], ids=['b', 'a', 'c'], k=1)
        b = run([.5, .5, .5], ids=['c', 'b', 'a'], k=1)
        self.assertEqual([x['id'] for x in a['inspect']], ['a', 'b', 'c'])
        self.assertEqual([x['id'] for x in b['inspect']], ['a', 'b', 'c'])

    def test_rejects_bad_input(self):
        for bad in ([], [math.nan, .1], [math.inf, .1], [None, .1]):
            with self.assertRaises(ValueError):
                run(bad)
        for k in (0, -.1, 1.1):
            with self.assertRaises(ValueError):
                run([.1, .2], k=k)
        with self.assertRaises(ValueError):
            run([.1, .2], ids=['a', 'a'])

    def test_rejects_group_leakage_and_missing_interval(self):
        with self.assertRaises(ValueError):
            run([.1, .2], groups=['g1', 'g2'], train_groups=['g2'])
        with self.assertRaises(TypeError):
            rank_budget_report([.1], ['a'], ['g'], .5)
        with self.assertRaises(ValueError):
            rank_budget_report([.1], ['a'], ['g'], .5, label_reliability_interval=(.1, math.nan))

    def test_no_operational_imports(self):
        tree = ast.parse((ROOT / 'card_condition/rank_budget.py').read_text())
        names = {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(names, {'math'})


class CardLevelTest(unittest.TestCase):
    S, G, T = [.9, .2, .4, .6, .1, .3], ['a', 'a', 'b', 'b', 'c', 'c'], [1, 0, 0, 0, 0, 0]

    def test_card_score_is_max(self):
        self.assertEqual(card_scores(self.S, self.G), {'a': .9, 'b': .6, 'c': .3})

    def test_operating_points(self):
        r = card_operating_points(self.S, self.G, self.T, [.5, .95], label_reliability_interval=REL)
        self.assertEqual((r['defect_cards'], r['normal_cards'], r['unit']), (1, 2, 'card'))
        self.assertEqual(r['points'][0]['defect_cards_found'], '1/1')
        self.assertEqual(r['points'][0]['normal_cards_flagged'], '1/2')
        self.assertEqual(r['points'][1]['defect_cards_found'], '0/1')
        self.assertIs(r['independent_validation'], False)
        self.assertGreater(r['points'][0]['false_alarm_upper95'], r['points'][0]['false_alarm'])

    def test_rejects_bad_card_input(self):
        for s, g, t in (([], [], []), ([math.nan], ['a'], [1]), ([.1, .2], ['a', 'b'], [1, 2]), ([.1, .2], ['a', 'b'], [1, 1])):
            with self.assertRaises(ValueError):
                card_operating_points(s, g, t, [.5], label_reliability_interval=REL)


if __name__ == '__main__':
    unittest.main()
