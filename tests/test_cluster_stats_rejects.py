"""Review 2026-11-27 I-1 (and the one-photo minor): the exact inputs that passed silently."""
import unittest

from tests.test_cluster_stats import stats

ROWS = [dict(id=str(i), target=1, group=str(i), image_sha256=str(i), box=[0, 0, 1, 1]) for i in range(20)]
GOOD = dict(rows=ROWS, scores=[.9] * 20)


class ClusterStatsRejectTest(unittest.TestCase):
    def test_bad_control_scores_are_refused(self):
        for bad in (float('nan'), 7.0, True, '0.9'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                stats.report(GOOD, dict(rows=ROWS, scores=[bad] * 20))

    def test_duplicate_candidate_rows_are_refused(self):
        with self.assertRaises(ValueError):
            stats.report(dict(rows=ROWS + ROWS, scores=[.9] * 40), GOOD)

    def test_missing_identity_field_is_not_a_match(self):
        bare = [{k: r[k] for k in ('id', 'target', 'group')} for r in ROWS]
        with self.assertRaises(ValueError):
            stats.report(dict(rows=bare, scores=[.9] * 20), dict(rows=bare, scores=[.9] * 20))

    def test_one_photo_gives_no_interval(self):
        one = {'a': [20, 40]}
        self.assertEqual((stats.rate(one)['wilson95'], stats.bootstrap(one)), (None, None))


if __name__ == '__main__':
    unittest.main()
