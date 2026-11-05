import importlib.util
from pathlib import Path
import unittest

import torch
from card_condition.detail_bag import detail_bag_loss
from test_same_photo_surface_ranking import fixture, objective as cold

PATH=Path(__file__).resolve().parents[1]/'tools/experiments/surface-ranking-warm-start-20261028/objective.py'
spec=importlib.util.spec_from_file_location('warm_ranking',PATH)
warm=importlib.util.module_from_spec(spec)
spec.loader.exec_module(warm)


class RankingWarmStartTest(unittest.TestCase):
    def test_zero_initialization_recovers_cold_fit(self):
        x,masks,y,tokens,mass,rows=fixture()
        before=cold.fit_rank_head(x,masks,y,tokens,mass,rows,normal_reduction='max_bound')
        after=warm.fit_warm_rank_head(x,masks,y,tokens,mass,rows,torch.zeros(2),torch.tensor(0.),normal_reduction='max_bound')
        self.assertTrue(torch.allclose(before[0],after[0],atol=2e-6,rtol=0))
        self.assertTrue(torch.allclose(before[1],after[1],atol=2e-6,rtol=0))
        self.assertAlmostEqual(before[2]['train_objective'],after[2]['train_objective'],places=8)

    def test_stationary_restart_preserves_head_inputs_and_objective(self):
        x,masks,y,tokens,mass,rows=fixture()
        before=cold.fit_rank_head(x,masks,y,tokens,mass,rows,normal_reduction='max_bound')
        weight,bias=before[0].clone(),before[1].clone()
        after=warm.fit_warm_rank_head(x,masks,y,tokens,mass,rows,weight,bias,normal_reduction='max_bound')
        self.assertTrue(torch.equal(weight,before[0]) and torch.equal(bias,before[1]))
        self.assertTrue(torch.allclose(before[0],after[0],atol=1e-5,rtol=0))
        self.assertLessEqual(after[2]['train_objective'],after[2]['initial_objective']+1e-8)
        self.assertLessEqual(after[2]['initial_logit_replay_error'],1e-8)

    def test_initial_objective_matches_same_raw_loss_and_pair_gradient(self):
        x,masks,y,tokens,mass,rows=fixture()
        w=torch.tensor([.2,-.3]);b=torch.tensor(.1)
        logits=x.double()@w.double()+b.double();normalized=mass.double()/mass.double().sum()
        base=sum(normalized[i]*detail_bag_loss(logits[i],int(y[i]),masks[i],None if tokens[i]<0 else int(tokens[i]),'max_bound') for i in range(len(x)))
        pairs=cold.training_pairs(rows,tokens)
        expected=float(base+.5*w.double().square().sum()+cold.same_photo_ranking_loss(logits,masks,tokens,normalized,pairs))
        after=warm.fit_warm_rank_head(x,masks,y,tokens,mass,rows,w,b,normal_reduction='max_bound')
        self.assertAlmostEqual(expected,after[2]['initial_objective'],places=10)
        self.assertLessEqual(after[2]['initial_logit_replay_error'],1e-8)
        v0=logits.detach().clone().requires_grad_();v1=logits.detach().clone().requires_grad_()
        old=cold.same_photo_ranking_loss(v0,masks,tokens,normalized,pairs)
        new=warm.same_photo_ranking_loss(v1,masks,tokens,normalized,pairs)
        old.backward();new.backward()
        self.assertTrue(torch.equal(old,new) and torch.equal(v0.grad,v1.grad))

    def test_invalid_initial_shape_or_nonfinite_bias_rejected(self):
        x,masks,y,tokens,mass,rows=fixture()
        for w,b in ((torch.zeros(3),torch.tensor(0.)),(torch.zeros(2),torch.tensor(float('nan'))),(torch.zeros(2),torch.zeros(1))):
            with self.subTest(shape=w.shape,bias=b),self.assertRaises(ValueError):
                warm.fit_warm_rank_head(x,masks,y,tokens,mass,rows,w,b,normal_reduction='max_bound')
