"""Hand-calculated contracts for paired miss transitions between two runs."""
import unittest
from card_condition.defect_regressions import defect_regressions

KEY = 'edge_defect'


def error(name, kind='fn', label=KEY):
    return dict(id=name, label=label, kind=kind, area='upper_left', group=name)


class PairedMissContractTest(unittest.TestCase):
    def regress(self, old, new, labels=(KEY,)):
        return defect_regressions(old, new, list(labels))

    def test_transitions_counts_and_evidence_sides(self):
        old = [error('a'), error('b'), error('x', 'fp')]
        new = [error('b'), error('c'), error('y', 'fp'), error('z', 'fp')]
        r = self.regress(old, new)[KEY]
        self.assertEqual((['c'], ['a'], ['b']), ([e['id'] for e in r['newly_missed']], [e['id'] for e in r['recovered']],
                                                  [e['id'] for e in r['still_missed']]))
        self.assertEqual((1, 1, 1, 1), (r['new_miss_count'], r['recovered_count'], r['persistent_miss_count'], r['false_positive_change']))
        # counts add up to each run's own miss total
        self.assertEqual((2, 2), (r['new_miss_count'] + r['persistent_miss_count'], r['recovered_count'] + r['persistent_miss_count']))
        self.assertFalse(r['recall_improvement_without_regression'])

    def test_improvement_needs_recovery_no_new_miss_and_no_extra_false_positive(self):
        old = [error('a'), error('b'), error('x', 'fp'), error('y', 'fp')]
        cases = [([error('b'), error('x', 'fp'), error('y', 'fp')], True),
                 ([error('b'), error('x', 'fp')], True),
                 ([error('b'), error('x', 'fp'), error('y', 'fp'), error('z', 'fp')], False),
                 ([error('b'), error('c'), error('x', 'fp')], False),
                 (old, False), ([], True)]
        for new, expected in cases:
            with self.subTest(new=[e['id'] + e['kind'] for e in new]):
                self.assertIs(expected, self.regress(old, new)[KEY]['recall_improvement_without_regression'])

    def test_swapping_runs_swaps_new_and_recovered_and_labels_stay_apart(self):
        old = [error('a'), error('k', label='surface_defect'), error('p', 'fp', 'surface_defect')]
        new = [error('b'), error('k', label='surface_defect'), error('q', 'fp', 'surface_defect'), error('r', 'fp', 'surface_defect')]
        forward, backward = self.regress(old, new, (KEY, 'surface_defect')), self.regress(new, old, (KEY, 'surface_defect'))
        self.assertEqual((['b'], ['a']), ([e['id'] for e in forward[KEY]['newly_missed']], [e['id'] for e in forward[KEY]['recovered']]))
        self.assertEqual((['a'], ['b']), ([e['id'] for e in backward[KEY]['newly_missed']], [e['id'] for e in backward[KEY]['recovered']]))
        self.assertEqual((0, 0, 1), (forward['surface_defect']['new_miss_count'], forward['surface_defect']['recovered_count'],
                                     forward['surface_defect']['persistent_miss_count']))
        # A false positive of another kind never counts against this kind.
        self.assertEqual((0, 1), (forward[KEY]['false_positive_change'], forward['surface_defect']['false_positive_change']))
        self.assertEqual(['edge_defect'], list(self.regress(old, new)))


if __name__ == '__main__':
    unittest.main()
