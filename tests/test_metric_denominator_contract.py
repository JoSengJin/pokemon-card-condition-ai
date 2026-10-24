"""Hand-calculated denominators and percentage-point changes of quality_rates."""
import unittest
from card_condition.quality_rates import error_rates, rate_change

REFERENCE = dict(tp=3, fn=1, tn=6, fp=4)


class DenominatorContractTest(unittest.TestCase):
    def test_each_class_has_its_own_denominator_and_zero_is_none(self):
        cases = [  # counts, positive, negative, FNR, FPR, accuracy
            (REFERENCE, 4, 10, 1/4, 4/10, 9/14),
            (dict(tp=0, fn=0, tn=0, fp=0), 0, 0, None, None, None),
            (dict(tp=2, fn=1, tn=0, fp=0), 3, 0, 1/3, None, 2/3),
            (dict(tp=0, fn=0, tn=3, fp=2), 0, 5, None, 2/5, 3/5),
            (dict(tp=0, fn=4, tn=0, fp=6), 4, 6, 1, 1, 0)]
        for counts, positive, negative, fnr, fpr, accuracy in cases:
            with self.subTest(counts=counts):
                r = error_rates(counts)
                self.assertEqual((positive, negative, positive+negative), (r['positive'], r['negative'], r['scored']))
                for key, expected in (('false_negative_rate', fnr), ('false_positive_rate', fpr), ('accuracy', accuracy)):
                    if expected is None:
                        self.assertIsNone(r[key])
                    else:
                        self.assertAlmostEqual(expected, r[key], places=12)

    def test_percentage_points_on_identical_denominators(self):
        cases = [  # candidate, delta FN, delta FP, delta accuracy, jointly improved
            (dict(tp=4, fn=0, tn=7, fp=3), -25, -10, 100*2/14, True),
            (dict(tp=2, fn=2, tn=5, fp=5), 25, 10, -100*2/14, False),
            (dict(tp=2, fn=2, tn=9, fp=1), 25, -30, 100*2/14, False),  # accuracy alone improves
            (dict(tp=3, fn=1, tn=6, fp=4), 0, 0, 0, False),
            (dict(tp=4, fn=0, tn=6, fp=4), -25, 0, 100/14, True)]
        for candidate, fn, fp, accuracy, jointly in cases:
            with self.subTest(candidate=candidate):
                r = rate_change(REFERENCE, candidate)
                delta = r['change_percentage_points']
                for key, expected in (('false_negative_rate', fn), ('false_positive_rate', fp), ('accuracy', accuracy)):
                    self.assertAlmostEqual(expected, delta[key], places=9)
                self.assertIs(jointly, r['errors_jointly_improved'])

    def test_one_class_change_is_not_a_joint_improvement(self):
        r = rate_change(dict(tp=0, fn=0, tn=3, fp=2), dict(tp=0, fn=0, tn=4, fp=1))
        self.assertIsNone(r['change_percentage_points']['false_negative_rate'])
        self.assertAlmostEqual(-20, r['change_percentage_points']['false_positive_rate'], places=9)
        self.assertFalse(r['errors_jointly_improved'])
        r = rate_change(dict(tp=1, fn=2, tn=0, fp=0), dict(tp=3, fn=0, tn=0, fp=0))
        self.assertIsNone(r['change_percentage_points']['false_positive_rate'])
        self.assertFalse(r['errors_jointly_improved'])

    def test_equal_rates_on_other_denominators_are_refused(self):
        # 1/4 and 2/8 are the same rate, but a different cohort is never a comparison.
        for candidate in (dict(tp=6, fn=2, tn=12, fp=8), dict(tp=4, fn=1, tn=6, fp=3), dict(tp=3, fn=1, tn=7, fp=4)):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(ValueError, 'denominators differ'):
                rate_change(REFERENCE, candidate)

    def test_malformed_counts_are_rejected(self):
        for bad in (dict(REFERENCE, extra=0), dict(tp=3, fn=1, tn=6), dict(REFERENCE, fp=None),
                    dict(REFERENCE, fp='4'), dict(REFERENCE, fn=False)):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'confusion counts'):
                error_rates(bad)


if __name__ == '__main__':
    unittest.main()
