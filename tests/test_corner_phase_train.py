import copy
import importlib.util
import unittest
from collections import Counter
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
VIEWS = [(0, 0), (7, 7)]
ROWS = [dict(id='a/1', group='ebay-a', image='pa', target=1), dict(id='a/2', group='ebay-a', image='pa', target=0),
        dict(id='b/1', group='b', image='pb', target=1), dict(id='b/2', group='b', image='pb', target=0),
        dict(id='c/1', group='c', image='pc', target=0), dict(id='c/2', group='c', image='pc', target=0),
        dict(id='d/1', group='d', image='pd', target=0)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tr = load('phase_transform', 'tools/experiments/corner-phase-train-20261124/transform.py')
try:
    CHAIN = load('card_rank_head', 'tools/experiments/corner-card-ranking-20261121/head.py')
except ModuleNotFoundError as exc:  # ignored confounder_head dependency absent in worktrees
    CHAIN = exc


def ref_terms(rows, s, tau=.1):
    """Re-implementation (copied formulas, NOT the real modules) of mass normalization, same-photo pair loss and
    card-pair loss, so the invariance argument is checked even when the ignored dependency is absent."""
    count = Counter(r['group'] for r in rows)
    y = torch.tensor([r['target'] for r in rows])
    mass = torch.tensor([1 / count[r['group']] for r in rows], dtype=torch.float64)
    ebay = torch.tensor([r['group'].startswith('ebay') for r in rows])
    mass[ebay] *= mass[~ebay].sum() / mass[ebay].sum()
    mass[y == 1] *= mass[y == 0].sum() / mass[y == 1].sum()
    photos, cards = {}, {}
    for i, r in enumerate(rows):
        photos.setdefault(r['image'], ([], []))[0 if r['target'] else 1].append(i)
        cards.setdefault(r['group'], []).append(i)
    photo = torch.stack([F.softplus(-(s[torch.tensor(p)][:, None] - s[torch.tensor(n)][None, :])).mean()
                         for p, n in photos.values() if p and n]).mean()
    card = {g: tau * (torch.logsumexp(s[torch.tensor(v)] / tau, 0) - torch.tensor(float(len(v))).log()) for g, v in cards.items()}
    defect = torch.stack([c for g, c in card.items() if any(rows[i]['target'] for i in cards[g])])
    normal = torch.stack([c for g, c in card.items() if not any(rows[i]['target'] for i in cards[g])])
    return mass / mass.sum(), photo, F.softplus(normal[None, :] - defect[:, None]).mean()


class PhaseTrainTest(unittest.TestCase):
    def test_expand_rows_order_ids_fields_and_no_mutation(self):
        before = copy.deepcopy(ROWS)
        out = tr.expand_rows(ROWS, VIEWS)
        self.assertEqual(ROWS, before)
        self.assertEqual(len(out), 2 * len(ROWS))
        self.assertEqual(len({r['id'] for r in out}), len(out))
        for v in range(2):
            for r, o in zip(ROWS, out[v * len(ROWS):(v + 1) * len(ROWS)], strict=True):
                self.assertEqual({k: o[k] for k in o if k != 'id'}, {k: r[k] for k in r if k != 'id'})
                self.assertTrue(o['id'].startswith(r['id'] + '@'))
        out[0]['group'] = 'changed'
        self.assertEqual(ROWS, before)

    def test_folds_keep_duplicates_together_and_stack_is_view_major(self):
        fold = {'ebay-a': 0, 'b': 1, 'c': 0, 'd': 1}
        for f in range(2):
            train = [r for r in ROWS if fold[r['group']] != f]
            hold = [r for r in ROWS if fold[r['group']] == f]
            e_train, e_hold = tr.expand_rows(train, VIEWS), tr.expand_rows(hold, VIEWS)
            self.assertFalse({r['group'] for r in e_train} & {r['group'] for r in e_hold})
            self.assertFalse({r['image'] for r in e_train} & {r['image'] for r in e_hold})
            self.assertEqual(Counter(r['group'] for r in e_train), Counter({g: 2 * n for g, n in Counter(r['group'] for r in train).items()}))
        a, b = torch.arange(12.).reshape(4, 3), torch.arange(12.).reshape(4, 3) + 100
        out = tr.stack_views([a, b], [3, 1], torch.float64)
        self.assertEqual(out.dtype, torch.float64)
        torch.testing.assert_close(out, torch.stack([a[3], a[1], b[3], b[1]]).double())
        m = tr.stack_views([a.numpy() > 5, b.numpy() > 5], [0, 2], torch.bool)
        self.assertEqual((m.dtype, m.tolist()), (torch.bool, [[False] * 3, [True] * 3, [True] * 3, [True] * 3]))

    def test_terms_invariant_to_duplication_reimplemented(self):
        torch.manual_seed(0)
        s = torch.randn(len(ROWS), dtype=torch.float64)
        mass, photo, card = ref_terms(ROWS, s)
        mass2, photo2, card2 = ref_terms(tr.expand_rows(ROWS, VIEWS), torch.cat([s, s]))
        torch.testing.assert_close(mass2.sum(), torch.tensor(1., dtype=torch.float64))
        torch.testing.assert_close(mass2[:len(ROWS)] + mass2[len(ROWS):], mass)
        self.assertAlmostEqual(float((mass2 * torch.cat([s, s])).sum()), float((mass * s).sum()), places=12)
        torch.testing.assert_close(photo2, photo)
        torch.testing.assert_close(card2, card)

    @unittest.skipIf(isinstance(CHAIN, Exception), f'real head chain not importable (ignored dependency missing): {CHAIN}')
    def test_real_chain_terms_and_fit_match_single_view(self):
        torch.manual_seed(1)
        big = tr.expand_rows(ROWS, VIEWS)
        x, masks = torch.randn(len(ROWS), 4, 3), torch.ones((len(ROWS), 4), dtype=torch.bool)
        s = torch.randn(len(ROWS), dtype=torch.float64)
        _, mass = CHAIN.corner.guarded_masses(ROWS)
        _, mass2 = CHAIN.corner.guarded_masses(big)
        torch.testing.assert_close(mass2[:len(ROWS)] + mass2[len(ROWS):], mass)
        torch.testing.assert_close(CHAIN.card_pair_loss(s, *CHAIN.card_indices(ROWS)),
                                   CHAIN.card_pair_loss(torch.cat([s, s]), *CHAIN.card_indices(big)))
        photo = [torch.stack([F.softplus(-(v[p][:, None] - v[n][None, :])).mean() for p, n in CHAIN.pair.photo_pairs(rows)]).mean()
                 for rows, v in ((ROWS, s), (big, torch.cat([s, s])))]
        torch.testing.assert_close(photo[0], photo[1])
        CHAIN.pair.masses = CHAIN.corner.guarded_masses
        a = CHAIN.fit(x, masks, ROWS, 1.0)
        b = CHAIN.fit(tr.stack_views([x, x], list(range(len(ROWS))), torch.float32), torch.cat([masks, masks]), big, 1.0)
        torch.testing.assert_close(a[0], b[0], atol=1e-5, rtol=1e-4)
        torch.testing.assert_close(a[1], b[1], atol=1e-5, rtol=1e-4)
        self.assertAlmostEqual(a[2]['train_objective'], b[2]['train_objective'], places=6)
