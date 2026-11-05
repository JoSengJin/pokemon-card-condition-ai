"""Small exhaustive and metamorphic checks over explicit value lists; no randomness."""
import itertools
import time
import unittest
from card_condition.quality_rates import error_rates, rate_change
from card_condition.regression_audit import compare_predictions
from card_condition.score_diagnostics import score_diagnostics
from test_ranking_abstention_contract import KEY, pairwise_auc, prediction

TIED = (.2, .5, .8)
DISTINCT = (.1, .3, .6, .9)


def cohorts(values=TIED, sizes=(2, 3, 4)):
    """Every truth/score assignment over the given values with both truth classes present."""
    for n in sizes:
        for truth in itertools.product((0, 1), repeat=n):
            if len(set(truth)) == 2:
                for scores in itertools.product(values, repeat=n):
                    yield list(truth), list(scores)


class MetamorphicContractTest(unittest.TestCase):
    def test_exhaustive_auroc_and_untied_ap_match_independent_formulas(self):
        started, checked = time.monotonic(), 0
        for truth, scores in cohorts():
            r = score_diagnostics([prediction(t, s, f'g{i}') for i, (t, s) in enumerate(zip(truth, scores))], [KEY])[KEY]
            positives = [s for t, s in zip(truth, scores) if t]
            negatives = [s for t, s in zip(truth, scores) if not t]
            self.assertAlmostEqual(pairwise_auc(positives, negatives), r['auroc'], places=12, msg=(truth, scores))
            self.assertTrue(0 <= r['average_precision'] <= 1)
            checked += 1
        for n in (2, 3, 4):
            for scores in itertools.permutations(DISTINCT, n):
                for truth in itertools.product((0, 1), repeat=n):
                    if len(set(truth)) < 2:
                        continue
                    r = score_diagnostics([prediction(t, s) for t, s in zip(truth, scores)], [KEY])[KEY]
                    # Without ties AP is the mean precision at each positive's rank.
                    ranks = [sum(s >= p for s in scores) for p, t in zip(scores, truth) if t]
                    hits = [sum(t and s >= p for s, t in zip(scores, truth)) for p, t in zip(scores, truth) if t]
                    expected = sum(h / k for h, k in zip(hits, ranks)) / len(ranks)
                    self.assertAlmostEqual(expected, r['average_precision'], places=12, msg=(truth, scores))
                    checked += 1
        # 1,314 tied cohorts + 504 untied cohorts; the budget keeps this a small, fixed enumeration.
        self.assertEqual(1314 + 504, checked)
        self.assertLess(time.monotonic() - started, 30)

    def test_row_permutations_change_nothing(self):
        for truth, scores in cohorts(sizes=(3,)):
            rows = [prediction(t, s, f'g{i}') for i, (t, s) in enumerate(zip(truth, scores))]
            after = [round(1 - s, 1) for s in scores]
            base = score_diagnostics(rows, [KEY])[KEY]
            paired = compare_predictions(truth, scores, after)
            for order in itertools.permutations(range(3)):
                r = score_diagnostics([rows[i] for i in order], [KEY])[KEY]
                for field in ('auroc', 'average_precision', 'rates_at_05', 'known', 'groups', 'warning_at_05'):
                    self.assertEqual(base[field], r[field], msg=(field, truth, scores, order))
                for a, b in zip(base['abstention_trials'], r['abstention_trials']):
                    for field in ('accepted', 'deferred_known', 'errors', 'risk_known', 'mean_group_risk',
                                  'accepted_groups', 'zero_accepted_known_groups'):
                        self.assertEqual(a[field], b[field], msg=(field, truth, scores, order))
                q = compare_predictions([truth[i] for i in order], [scores[i] for i in order], [after[i] for i in order])
                self.assertEqual((paired['before'], paired['after']), (q['before'], q['after']))
                for field in ('new_misses', 'new_false_positives', 'recovered'):
                    self.assertEqual(sorted(order[i] for i in q[field]), paired[field])

    def test_duplicated_cohort_doubles_counts_but_keeps_rates(self):
        for truth, scores in cohorts(sizes=(3,)):
            rows = [prediction(t, s, f'g{i}') for i, (t, s) in enumerate(zip(truth, scores))]
            once, twice = (score_diagnostics(r, [KEY])[KEY] for r in (rows, rows + rows))
            self.assertEqual((2 * once['positive'], 2 * once['negative']), (twice['positive'], twice['negative']))
            for field in ('auroc', 'average_precision', 'balanced_accuracy_at_05'):
                self.assertAlmostEqual(once[field], twice[field], places=12)
            for field in ('false_negative_rate', 'false_positive_rate', 'accuracy'):
                self.assertAlmostEqual(once['rates_at_05'][field], twice['rates_at_05'][field], places=12)
            for a, b in zip(once['abstention_trials'], twice['abstention_trials']):
                self.assertEqual((2 * a['accepted'], 2 * a['errors'], a['accepted_groups']),
                                 (b['accepted'], b['errors'], b['accepted_groups']))
                for field in ('risk_known', 'mean_group_risk', 'coverage_known'):
                    if a[field] is None:
                        self.assertIsNone(b[field])
                    else:
                        self.assertAlmostEqual(a[field], b[field], places=12)
        for counts in (dict(tp=3, fn=1, tn=6, fp=4), dict(tp=0, fn=2, tn=5, fp=0)):
            doubled = error_rates({k: 2 * v for k, v in counts.items()})
            for field in ('false_negative_rate', 'false_positive_rate', 'accuracy'):
                self.assertEqual(error_rates(counts)[field], doubled[field])

    def test_identical_runs_report_no_change(self):
        for truth, scores in cohorts():
            r = compare_predictions(truth, scores, scores)
            self.assertEqual(r['before'], r['after'])
            self.assertEqual(([], [], []), (r['new_misses'], r['new_false_positives'], r['recovered']))
            self.assertTrue(r['no_new_errors'])
            self.assertFalse(r['aggregate_improved'] or r['informative_improvement'])
            change = rate_change(r['before'], r['after'])
            self.assertEqual({0}, {v for v in change['change_percentage_points'].values() if v is not None})
            self.assertFalse(change['errors_jointly_improved'])

    def test_crossing_the_threshold_moves_exactly_one_confusion_cell(self):
        cases = [  # truth, before, after, cell before -> cell after, transition list
            (1, .4999, .5, 'fn', 'tp', 'recovered'), (1, .5, .4999, 'tp', 'fn', 'new_misses'),
            (0, .4999, .5, 'tn', 'fp', 'new_false_positives'), (0, .5, .4999, 'fp', 'tn', 'recovered')]
        fixed_truth, fixed_scores = [1, 0], [.9, .1]
        for truth, before, after, old, new, transition in cases:
            with self.subTest(truth=truth, before=before, after=after):
                r = compare_predictions(fixed_truth + [truth], fixed_scores + [before], fixed_scores + [after])
                moved = {k: r['after'][k] - r['before'][k] for k in r['before']}
                self.assertEqual({old: -1, new: 1}, {k: v for k, v in moved.items() if v})
                self.assertEqual([2], r[transition])
                rows = [prediction(t, s) for t, s in zip(fixed_truth + [truth], fixed_scores + [after])]
                rates = score_diagnostics(rows, [KEY])[KEY]['rates_at_05']
                self.assertEqual(r['after'], dict(tp=rates['positive'] - round(rates['false_negative_rate'] * rates['positive']),
                                                  fn=round(rates['false_negative_rate'] * rates['positive']),
                                                  tn=rates['negative'] - round(rates['false_positive_rate'] * rates['negative']),
                                                  fp=round(rates['false_positive_rate'] * rates['negative'])))


if __name__ == '__main__':
    unittest.main()
