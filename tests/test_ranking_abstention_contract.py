"""AUROC/AP ties and single-class sets, abstention boundaries and per-card denominators."""
import unittest
from card_condition.score_diagnostics import score_diagnostics

KEY = 'edge_defect'
TRIALS = ((.1, .9), (.2, .8), (.3, .7), (.4, .6), (.5, .5))


def prediction(truth, score, group='g'):
    return dict(labels={KEY: truth}, probabilities={KEY: score}, group=group)


def pairwise_auc(positives, negatives):
    """Independent Mann-Whitney count: win 1, tie 0.5, loss 0 over every positive-negative pair."""
    wins = sum(1 if p > n else .5 if p == n else 0 for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


class RankingAbstentionContractTest(unittest.TestCase):
    def test_auroc_and_ap_match_hand_calculation(self):
        cases = [  # name, positive scores, negative scores, AUROC, AP (see report table)
            ('separated', [.9, .8], [.2, .1], 1, 1),
            ('reversed', [.1, .2], [.8, .9], 0, 5/12),
            ('all tied', [.5, .5], [.5], .5, 2/3),
            ('partial tie', [.8, .6], [.6, .3], .875, 5/6),
            ('three by three', [.9, .4, .3], [.7, .4, .1], 11/18, 7/10),
            ('one by three', [.5], [.6, .5, .4], .5, 1/3)]
        for name, positives, negatives, auroc, ap in cases:
            rows = [prediction(1, v) for v in positives] + [prediction(0, v) for v in negatives]
            for order in (rows, rows[::-1], rows[1:] + rows[:1]):
                with self.subTest(case=name, first=order[0]['probabilities'][KEY]):
                    r = score_diagnostics(order, [KEY])[KEY]
                    self.assertAlmostEqual(pairwise_auc(positives, negatives), auroc, places=12)
                    self.assertAlmostEqual(auroc, r['auroc'], places=12)
                    self.assertAlmostEqual(ap, r['average_precision'], places=12)

    def test_single_class_or_unknown_only_sets_report_none(self):
        for name, rows in (('positives only', [prediction(1, .9), prediction(1, .2)]),
                           ('negatives only', [prediction(0, .9), prediction(0, .2)]),
                           ('unknown only', [prediction(None, .9)]), ('empty', [])):
            with self.subTest(case=name):
                r = score_diagnostics(rows, [KEY])[KEY]
                for field in ('auroc', 'average_precision', 'balanced_accuracy_at_05'):
                    self.assertIsNone(r[field])
                self.assertEqual('both_truth_classes_required', r['warning_at_05'])

    def test_each_trial_uses_half_open_boundaries(self):
        for low, high in TRIALS:
            with self.subTest(low=low, high=high):
                # below low -> normal, exactly low -> deferred unless low == high, exactly high -> defect
                rows = [prediction(0, round(low - .05, 2)), prediction(1, low), prediction(1, high),
                        prediction(0, round((low + high) / 2, 2))]
                trial = next(t for t in score_diagnostics(rows, [KEY])[KEY]['abstention_trials'] if t['normal_below'] == low)
                self.assertEqual(high, trial['defect_at_least'])
                if low < high:
                    self.assertEqual((2, 2, 0), (trial['accepted'], trial['deferred_known'], trial['errors']))
                else:
                    # .5/.5 equals the raw 0.5 decision: the midpoint .5 with truth 0 is a false defect.
                    self.assertEqual((4, 0, 1, 1, 0), (trial['accepted'], trial['deferred_known'], trial['errors'],
                                                       trial['false_defect'], trial['false_clean']))

    def test_raw_half_trial_agrees_with_rates_at_05(self):
        rows = [prediction(1, .5), prediction(0, .49), prediction(0, .5), prediction(1, .1), prediction(None, .5)]
        r = score_diagnostics(rows, [KEY])[KEY]
        trial = r['abstention_trials'][-1]
        rates = r['rates_at_05']
        self.assertEqual((.5, .5), (trial['normal_below'], trial['defect_at_least']))
        self.assertEqual((4, 2), (trial['accepted'], trial['errors']))
        self.assertEqual((1, 1), (trial['false_defect'], trial['false_clean']))
        self.assertEqual((1/2, 1/2), (rates['false_negative_rate'], rates['false_positive_rate']))
        self.assertEqual((4, 1), (r['known'], r['unknown']))

    def test_micro_risk_card_mean_and_deferred_cards_are_distinct(self):
        rows = [prediction(1, .9, 'X'), prediction(0, .8, 'X'), prediction(0, .75, 'X'), prediction(1, .1, 'Y'),
                prediction(0, .5, 'Z'), prediction(1, .4, 'Z'), prediction(None, .95, 'U')]
        r = score_diagnostics(rows, [KEY])[KEY]
        trial = next(t for t in r['abstention_trials'] if t['normal_below'] == .3)
        self.assertEqual((4, 2, 3), (trial['accepted'], trial['deferred_known'], trial['errors']))
        self.assertAlmostEqual(3/4, trial['risk_known'], places=12)
        self.assertAlmostEqual(5/6, trial['mean_group_risk'], places=12)
        self.assertAlmostEqual(4/6, trial['coverage_known'], places=12)
        self.assertEqual((2, 1), (trial['accepted_groups'], trial['zero_accepted_known_groups']))
        cards = trial['by_group']
        self.assertEqual(['U', 'X', 'Y', 'Z'], sorted(cards))
        self.assertEqual((2, 2, 0, 0), (cards['Z']['known'], cards['Z']['deferred_known'], cards['Z']['accepted'], cards['Z']['unknown']))
        self.assertEqual((0, 1, None, None), (cards['U']['known'], cards['U']['unknown'], cards['U']['coverage_known'], cards['U']['risk_known']))
        self.assertAlmostEqual(2/3, cards['X']['risk_known'], places=12)
        self.assertEqual((1, 2, 0, 0), (cards['X']['tp'], cards['X']['fp'], cards['X']['tn'], cards['X']['fn']))
        self.assertEqual((6, 1, 3), (r['known'], r['unknown'], r['groups']))


if __name__ == '__main__':
    unittest.main()
