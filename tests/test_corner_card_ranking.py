import importlib.util
from pathlib import Path

import unittest
import torch

PATH = Path(__file__).resolve().parents[1] / 'tools/experiments/corner-card-ranking-20261121/head.py'


def load_head():
    spec = importlib.util.spec_from_file_location('card_rank_head', PATH)
    head = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(head)
    return head


class CardRankingTest(unittest.TestCase):
    def test_reversed_card_pair_pushes_only_relevant_zones(self):
        self.assertTrue(PATH.is_file(), 'Card-pair loss is missing')
        head = load_head()
        rows = [dict(group='defect', target=1), dict(group='defect', target=0), dict(group='normal', target=0)]
        scores = torch.tensor([.25, .99, .75], dtype=torch.float64, requires_grad=True)
        loss = head.card_pair_loss(scores, *head.card_indices(rows))
        loss.backward()
        self.assertAlmostEqual(loss.item(), .974076984)
        torch.testing.assert_close(scores.grad, torch.tensor([-.622459331, 0, .622459331], dtype=torch.float64))


    def test_card_score_does_not_reward_repeating_identical_zones(self):
        head = load_head()
        rows = [dict(group='defect', target=1), dict(group='normal', target=0), dict(group='normal', target=0)]
        loss = head.card_pair_loss(torch.tensor([.75, .25, .25]), *head.card_indices(rows))
        self.assertAlmostEqual(loss.item(), .474076984)


    def test_zero_weight_reproduces_candidate_e_fit(self):
        head = load_head()
        x = torch.tensor([[[1., .1], [.9, 0.]], [[-.7, 0.], [-.9, -.2]],
                          [[.6, .3], [.4, .1]], [[-.4, 0.], [-.8, .3]]])
        masks = torch.ones((4, 2), dtype=torch.bool)
        rows = [dict(group='card-a', image='a', target=1), dict(group='card-a', image='a', target=0),
                dict(group='card-b', image='b', target=1), dict(group='card-c', image='c', target=0)]
        head.pair.masses = head.corner.guarded_masses
        reference = head.pair.fit_pair(x, masks, rows)
        trial = head.fit(x, masks, rows, 0.0)
        torch.testing.assert_close(reference[0], trial[0], atol=0, rtol=0)
        torch.testing.assert_close(reference[1], trial[1], atol=0, rtol=0)
