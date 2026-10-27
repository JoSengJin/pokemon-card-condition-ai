import importlib.util
from pathlib import Path
import unittest

import torch
from test_same_photo_surface_ranking import fixture, objective as rank_module

PATH=Path(__file__).resolve().parents[1]/'tools/experiments/surface-ranking-regression-cause-20261028/worker.py'
spec=importlib.util.spec_from_file_location('ranking_cause',PATH)
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class RankingCauseTest(unittest.TestCase):
    def test_additive_decomposition_peak_move_and_fixed_counterfactual(self):
        x=torch.tensor([[1.,0.],[0.,2.],[3.,9.]],dtype=torch.float64)
        mask=torch.tensor([True,True,False]);center=torch.tensor([.3,.4],dtype=torch.float64)
        value=worker.components(x,mask,torch.tensor([1.,0.]),torch.tensor(-.2),torch.tensor([0.,1.]),torch.tensor(-.3),center)
        self.assertEqual((0,1),(value['old_peak'],value['new_peak']))
        self.assertTrue(value['peak_changed'])
        self.assertAlmostEqual(value['delta_max_logit'],value['centered_bias_delta']+value['coefficient_at_old_peak']+value['peak_relocation'],places=12)
        self.assertLessEqual(value['additive_error'],1e-8)

    def test_center_origin_does_not_change_total_or_predictions(self):
        x=torch.tensor([[1.,0.],[0.,2.]],dtype=torch.float64);mask=torch.ones(2,dtype=torch.bool)
        w0=torch.tensor([.2,-.3]);w1=torch.tensor([.3,-.2])
        a=worker.components(x,mask,w0,torch.tensor(.1),w1,torch.tensor(-.1),torch.zeros(2))
        b=worker.components(x,mask,w0,torch.tensor(.1),w1,torch.tensor(-.1),torch.tensor([10.,-3.]))
        self.assertAlmostEqual(a['delta_max_logit'],b['delta_max_logit'],places=12)
        self.assertAlmostEqual(a['centered_bias_delta']+a['coefficient_at_old_peak'],b['centered_bias_delta']+b['coefficient_at_old_peak'],places=12)
        self.assertEqual(a['before_prediction'],b['before_prediction'])
        self.assertEqual(a['after_prediction'],b['after_prediction'])

    def test_analytic_pair_gradient_matches_autograd_and_shared_bias_cancels(self):
        x,masks,y,tokens,mass,rows=fixture();center,mass=worker.training_state(x,masks,tokens,rows)
        pairs=rank_module.training_pairs(rows,tokens)
        w0=torch.tensor([.2,-.3]);w1=torch.tensor([.3,-.25])
        first,grad0=worker.pair_readout(x,masks,tokens,mass,rows,pairs,center,w0,torch.tensor(.1),w1,torch.tensor(.12),rank_module)
        shifted,grad1=worker.pair_readout(x,masks,tokens,mass,rows,pairs,center,w0,torch.tensor(4.1),w1,torch.tensor(4.12),rank_module)
        self.assertLessEqual(first[0]['analytic_autograd_error'],1e-8)
        self.assertLessEqual(abs(first[0]['bias_gradient']),1e-10)
        self.assertAlmostEqual(first[0]['weighted_rank_loss_before'],shifted[0]['weighted_rank_loss_before'],places=10)
        self.assertTrue(torch.allclose(grad0[0],grad1[0],atol=1e-10,rtol=0))
