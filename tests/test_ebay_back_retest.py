import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ebay_back_retest as r  # noqa: E402


class RetestTest(unittest.TestCase):
    def test_draw_is_seeded_and_balanced(self):
        ans = {f'a{i}': '정상' for i in range(60)} | {f'b{i}': '제한' for i in range(30)} | {'m': '모름'}
        ids = r.draw(ans)
        self.assertEqual(ids, r.draw(ans))
        self.assertEqual([ans[i] for i in ids].count('제한'), 20)
        self.assertNotIn('m', ids)
        with self.assertRaises(ValueError):
            r.draw({'a': '정상'})

    def test_kappa_known_values(self):
        self.assertAlmostEqual(r.kappa([('정상', '정상')] * 5 + [('제한', '제한')] * 5), 1.0)
        # 8 of 10 agree, balanced marginals -> po .8 pe .5 -> .6
        self.assertAlmostEqual(r.kappa([('정상', '정상')] * 4 + [('제한', '제한')] * 4 + [('정상', '제한'), ('제한', '정상')]), 0.6)
        self.assertIsNone(r.kappa([('정상', '정상')] * 3))

    def test_score_counts_unusable_separately(self):
        first = {'x': '정상', 'y': '제한', 'z': '정상'}
        second = {'x': '정상', 'y': '정상', 'z': '모름'}
        s = r.score(first, second, boots=50)
        self.assertEqual((s['n'], s['used'], s['unusable'], s['agree']), (3, 2, 1, 1))
        self.assertEqual(s['first_limit_second_normal'], 1)


if __name__ == '__main__':
    unittest.main()
