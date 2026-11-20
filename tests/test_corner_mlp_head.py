import importlib.util
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'tools/experiments/corner-mlp-head-20261121'


def load(name):
    spec = importlib.util.spec_from_file_location('mlp_' + name, DIR / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def problem(seed=0):
    """Twelve photos (6 mixed, 6 normal-only), 2 zones each: tokens 6 x dim 5, a strong first-token signal marks defect zones."""
    g = torch.Generator().manual_seed(seed)
    rows, x = [], torch.randn(24, 6, 5, generator=g)
    for p in range(12):
        for z in range(2):
            target = int(p < 6 and z == 0)
            rows.append(dict(id=f'g{p}/{z}', group=f'g{p}', image=f'img{p}', target=target, area=str(z)))
            x[2*p + z, 0, 0] += 6*target
    return rows, x, torch.ones(24, 6, dtype=torch.bool)


class HeadTest(unittest.TestCase):
    def test_linear_path_equals_pair_fit_pair(self):
        head = load('head')
        rows, x, m = problem()
        head.pair.masses = head.corner.guarded_masses
        coef, bias, _ = head.pair.fit_pair(x, m, rows)
        control = head.corner.sw.score(x, m, coef, bias)
        mine = head.score_head(x, m, head.fit_head(x, m, rows, 'linear', 0, 300), 'linear')
        self.assertGreater(max(control) - min(control), .2, 'control fit must be non-trivial for the equivalence to mean anything')
        for a, b in zip(control, mine):
            self.assertAlmostEqual(a, b, places=4)

    def test_mlp_init_is_seeded_and_output_layer_zero(self):
        head = load('head')
        a, b, c = (head.init_params('mlp', 5, s) for s in (7, 7, 8))
        self.assertTrue(torch.equal(a['w1'], b['w1']))
        self.assertFalse(torch.equal(a['w1'], c['w1']))
        self.assertEqual((5, head.HIDDEN), tuple(a['w1'].shape))
        self.assertEqual(0., float(a['w2'].abs().sum()))
        self.assertEqual(torch.float64, a['w1'].dtype)

    def test_mlp_fits_and_scores_are_finite_probabilities(self):
        head = load('head')
        rows, x, m = problem()
        fitted = head.fit_head(x, m, rows, 'mlp', 3, 1000)
        scores = head.score_head(x, m, fitted, 'mlp')
        self.assertTrue(all(0 <= s <= 1 for s in scores))
        self.assertLessEqual(fitted[2]['max_gradient'], 1e-5)
        pos = [s for s, r in zip(scores, rows) if r['target']]
        neg = [s for s, r in zip(scores, rows) if not r['target']]
        self.assertGreater(sum(pos)/len(pos), sum(neg)/len(neg))
        self.assertGreater(max(scores) - min(scores), .2, 'the fit must not collapse to a constant')

    def test_nonconvergence_raises(self):
        head = load('head')
        rows, x, m = problem()
        with self.assertRaises(ValueError):
            head.fit_head(x, m, rows, 'mlp', 3, 1)

    def test_penalty_covers_weights_not_biases_and_constants_frozen(self):
        head = load('head')
        self.assertEqual({'linear': ('w',), 'mlp': ('w1', 'w2')}, head.PENALIZED)
        self.assertEqual((64, 1000, 1.0), (head.HIDDEN, head.MAX_ITER, head.pair.LAMBDA))


class MatchedMissTest(unittest.TestCase):
    def test_card_miss_at_false_alarm_budget(self):
        worker = load('worker')
        rows = []
        for g, ts in dict(p1=[1, 0], p2=[1, 1], n1=[0, 0], n2=[0, 0], n3=[0, 0]).items():
            rows += [dict(group=g, target=t) for t in ts]
        scores = [.9, .1,  .3, .2,  .8, .1,  .5, .2,  .4, .4]
        # normal-card maxima: n1 .8, n2 .5, n3 .4; defect-card bests: p1 .9, p2 .3
        zero = worker.card_miss(rows, scores, 0)
        self.assertEqual((1, 2, 0, 3), (zero['miss'], zero['positives'], zero['false_alarm'], zero['normals']))
        one = worker.card_miss(rows, scores, 1)
        self.assertEqual((1, 1), (one['miss'], one['false_alarm']))
        two = worker.card_miss(rows, scores, 2)
        self.assertEqual((1, 2), (two['miss'], two['false_alarm']))
        fixed = worker.card_miss(rows, scores, 0, .35)
        self.assertEqual((1, 3), (fixed['miss'], fixed['false_alarm']))
        self.assertEqual(1, worker.card_miss(rows, scores, 99)['normals'] - 2)


if __name__ == '__main__':
    unittest.main()
