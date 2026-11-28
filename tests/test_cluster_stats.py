import importlib.util
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cluster_stats', ROOT / 'tools/diagnostics/cluster-stats-20261127/stats.py')
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)
DATA = Path(os.environ.get('CARD_CONDITION_DATA_ROOT', ROOT)) / 'artifacts/experiments'
MEAN = DATA / '20261121T050740-8588eeb0/observations.json'
OLD = DATA / '20261102T140143-82781117/observations.json'


class ClusterStatsTest(unittest.TestCase):
    def test_clustering_widens_and_zero_denominator_is_unmeasured(self):
        clumped = stats.rate({i: [4 if i < 5 else 0, 4] for i in range(20)})
        spread = stats.rate({i: [1, 4] for i in range(20)})
        self.assertGreater(clumped['deff'], 3)
        self.assertEqual(spread['deff'], 0)
        width = lambda r: r['wilson95'][1] - r['wilson95'][0]
        self.assertGreater(width(clumped), width(spread))
        self.assertEqual(stats.rate({})['rate'], None)

    def test_sign_flip_exact_and_sampled(self):
        self.assertEqual(stats.sign_flip([1] * 6), dict(photos=6, p=2 / 64, method='exact'))
        self.assertEqual(stats.sign_flip([])['p'], 1.0)
        self.assertEqual(stats.sign_flip([4])['p'], 1.0)  # one photo cannot prove anything, however many zones
        many = stats.sign_flip([1] * 25, flips=2000)
        self.assertEqual((many['method'], many['p']), ('sampled 2000', 1 / 2001))

    def test_mismatched_rows_are_refused(self):
        data = dict(rows=[dict(id='a', target=1, group='a')], scores=[.9])
        with self.assertRaises(ValueError):
            stats.report(data, dict(data, rows=[dict(id='b', target=1, group='a')]))

    @unittest.skipUnless(MEAN.is_file() and OLD.is_file(), '미검증: 실자료 없음')
    def test_real_scores_reproduce_published_numbers(self):
        mean = json.loads(MEAN.read_text())
        out = stats.report(mean, json.loads(OLD.read_text()))
        for name, expected, pair, pair_deff in (('miss', (89, 401, 175, 1.44), (15, 41), 1.19),
                                                ('false_alarm', (89, 541, 192, 1.33), (30, 26), 1.14)):
            got = out[name]
            self.assertEqual((got['k'], got['n'], got['photos'], round(got['deff'], 2)), expected)
            self.assertEqual((got['paired']['worse_b'], got['paired']['better_c']), pair)
            self.assertEqual((got['paired']['discordance']['photos'], round(got['paired']['discordance']['deff'], 2)),
                             (got['photos'], pair_deff))
            print(name, got['wilson95'], got['bootstrap95'], got['paired']['test'])


if __name__ == '__main__':
    unittest.main()
