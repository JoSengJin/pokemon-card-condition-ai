"""Paired comparison populations: same IDs, evidence and truth, judged per row."""
import copy
import unittest
from card_condition.regression_audit import compare_predictions, compare_runs

LABEL = 'surface_defect'


def rows(*items):
    return [dict(id=key, group='g-' + key, side='front', split='val', image_sha256=key * 8,
                 card_box=[0, 0, 1, 1], box=[0, 0, .3, .3], labels={LABEL: truth}) for key, truth in items]


class PairedPopulationContractTest(unittest.TestCase):
    def test_transitions_are_counted_per_row(self):
        # truth  before -> after : transition
        # 1      .1 -> .9        : recovered miss
        # 1      .9 -> .1        : new miss
        # 0      .1 -> .9        : new false positive
        # 0      .9 -> .1        : recovered false positive
        # 1      .9 -> .9, 0 .1 -> .1 : unchanged correct
        r = compare_predictions([1, 1, 0, 0, 1, 0], [.1, .9, .1, .9, .9, .1], [.9, .1, .9, .1, .9, .1])
        self.assertEqual((dict(tp=2, tn=2, fp=1, fn=1), dict(tp=2, tn=2, fp=1, fn=1)), (r['before'], r['after']))
        self.assertEqual(([1], [2], [0, 3]), (r['new_misses'], r['new_false_positives'], r['recovered']))
        self.assertFalse(r['aggregate_improved'])
        self.assertFalse(r['no_new_errors'])

    def test_improvement_flags_have_different_meanings(self):
        # FN 2 -> 1 with FP unchanged: aggregate and informative improvement, yet a new miss exists.
        r = compare_predictions([1, 1, 1, 0], [.1, .1, .9, .1], [.9, .9, .1, .1])
        self.assertEqual((2, 1, 0, 0), (r['before']['fn'], r['after']['fn'], r['before']['fp'], r['after']['fp']))
        self.assertTrue(r['aggregate_improved'])
        self.assertTrue(r['informative_improvement'])
        self.assertFalse(r['no_new_errors'])
        self.assertEqual([2], r['new_misses'])
        # FN falls but FP rises: no aggregate improvement even though accuracy is unchanged.
        r = compare_predictions([1, 1, 0, 0], [.1, .1, .1, .1], [.9, .9, .9, .9])
        self.assertFalse(r['aggregate_improved'])
        self.assertEqual(1, r['constant_prediction'])

    def test_row_order_does_not_change_the_result(self):
        before, after = rows(('a', 1), ('b', 0), ('c', 1)), rows(('a', 1), ('b', 0), ('c', 1))
        scores = {'a': (.2, .8), 'b': (.7, .3), 'c': (.9, .9)}
        expected = compare_runs(before, [scores[r['id']][0] for r in before], after, [scores[r['id']][1] for r in after], LABEL)
        for order in ([2, 0, 1], [1, 2, 0], [2, 1, 0]):
            with self.subTest(order=order):
                shuffled = [after[i] for i in order]
                result = compare_runs(before[::-1], [scores[r['id']][0] for r in before[::-1]],
                                      shuffled, [scores[r['id']][1] for r in shuffled], LABEL)
                self.assertEqual(expected, result)
        self.assertEqual((['a', 'b', 'c'], [], [], [0, 1]), (expected['ids'], expected['new_misses'],
                         expected['new_false_positives'], expected['recovered']))

    def test_changed_population_or_evidence_is_refused(self):
        base = rows(('a', 1), ('b', 0))
        for field, value in (('group', 'g-x'), ('side', 'back'), ('split', 'train'), ('image_sha256', 'x' * 8),
                             ('card_box', [0, 0, .9, 1]), ('box', [0, 0, .4, .3])):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'evidence changed'):
                changed = copy.deepcopy(base); changed[1][field] = value
                compare_runs(base, [.8, .2], changed, [.8, .2], LABEL)
        for after, scores, message in ((rows(('a', 1)), [.8], 'populations differ'),
                                       (rows(('a', 1), ('b', 0), ('c', 1)), [.8, .2, .9], 'populations differ'),
                                       (rows(('a', 1), ('z', 0)), [.8, .2], 'populations differ'),
                                       (rows(('a', 1), ('a', 1)), [.8, .8], 'Duplicate'),
                                       (rows(('a', 1), ('b', 0)), [.8], 'lengths differ')):
            with self.subTest(after=[r['id'] for r in after]), self.assertRaisesRegex(ValueError, message):
                compare_runs(base, [.8, .2], after, scores, LABEL)

    def test_unknown_truth_never_becomes_normal(self):
        known, unknown = rows(('a', 1), ('b', 0)), rows(('a', 1), ('b', None))
        with self.assertRaisesRegex(ValueError, 'Human truth changed'):
            compare_runs(unknown, [.8, .2], known, [.8, .2], LABEL)
        with self.assertRaisesRegex(ValueError, 'Human truth changed'):
            compare_runs(known, [.8, .2], unknown, [.8, .2], LABEL)
        # Unknown on both sides is not dropped silently; the whole comparison is refused.
        with self.assertRaisesRegex(ValueError, 'explicit binary'):
            compare_runs(unknown, [.8, .2], unknown, [.8, .2], LABEL)

    def test_valid_paired_input_is_counted_by_hand(self):
        base = rows(('a', 1), ('b', 1), ('c', 0), ('d', 0))
        r = compare_runs(base, [.4, .6, .5, .1], base, [.6, .6, .4, .1], LABEL)
        self.assertEqual(dict(tp=1, tn=1, fp=1, fn=1), r['before'])
        self.assertEqual(dict(tp=2, tn=2, fp=0, fn=0), r['after'])
        self.assertEqual(([], [], [0, 2]), (r['new_misses'], r['new_false_positives'], r['recovered']))
        self.assertTrue(r['aggregate_improved'] and r['informative_improvement'] and r['no_new_errors'])


if __name__ == '__main__':
    unittest.main()
