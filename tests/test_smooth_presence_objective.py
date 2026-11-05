import importlib.util
import math
from pathlib import Path
import unittest

import torch
from torch.nn import functional as F
from card_condition.detail_bag import detail_bag_loss, fit_detail_head

PATH=Path(__file__).resolve().parents[1]/'tools/experiments/surface-smooth-presence-20261027/objective.py'
spec=importlib.util.spec_from_file_location('smooth_presence_objective',PATH)
objective=importlib.util.module_from_spec(spec)
spec.loader.exec_module(objective)


class SmoothPresenceTest(unittest.TestCase):
    def test_normal_and_human_point_values_and_gradients_unchanged(self):
        for target,point in ((0,None),(1,1)):
            old=torch.tensor([-.3,.4,8.],dtype=torch.float64,requires_grad=True)
            new=old.detach().clone().requires_grad_()
            mask=torch.tensor([True,True,False])
            baseline=detail_bag_loss(old,target,mask,point,'max_bound')
            changed=objective.smooth_presence_loss(new,target,mask,point,'max_bound')
            baseline.backward();changed.backward()
            self.assertTrue(torch.equal(baseline,changed))
            self.assertTrue(torch.equal(old.grad,new.grad))

    def test_weak_equal_token_invariance_and_distributed_valid_gradient(self):
        mask=torch.tensor([True,True,False])
        equal=torch.tensor([.3,.3,8.],dtype=torch.float64)
        self.assertTrue(torch.allclose(detail_bag_loss(equal,1,mask,None,'max_bound'),
            objective.smooth_presence_loss(equal,1,mask,None,'max_bound'),atol=1e-12,rtol=0))
        values=torch.tensor([.3,.29,8.],dtype=torch.float64,requires_grad=True)
        loss=objective.smooth_presence_loss(values,1,mask,None,'max_bound')
        loss.backward()
        self.assertTrue((values.grad[:2]<0).all())
        self.assertEqual(0.,float(values.grad[2]))
        self.assertGreaterEqual(float(loss.detach()),float(F.softplus(-values[:2].max()).detach()))
        self.assertLessEqual(float(loss.detach()),float(F.softplus(-values[:2].max()+.1*math.log(2)).detach()))

    def test_no_weak_positive_fit_equals_original(self):
        torch.manual_seed(11)
        x=torch.randn(6,3,2);mask=torch.ones(6,3,dtype=torch.bool)
        y=torch.tensor([0,0,0,1,1,1]);points=torch.tensor([-1,-1,-1,0,1,2]);mass=torch.ones(6)
        before=fit_detail_head(x,mask,y,points,mass,normal_reduction='max_bound')
        after=objective.fit_smooth_presence(x,mask,y,points,mass,normal_reduction='max_bound')
        self.assertTrue(torch.allclose(before[0],after[0],atol=2e-6,rtol=0))
        self.assertTrue(torch.allclose(before[1],after[1],atol=2e-6,rtol=0))
        self.assertAlmostEqual(before[2]['train_objective'],after[2]['train_objective'],places=8)

    def test_weak_positive_fit_converges_and_invalid_human_point_stays_rejected(self):
        torch.manual_seed(11)
        x=torch.randn(6,3,2);mask=torch.ones(6,3,dtype=torch.bool)
        y=torch.tensor([0,0,0,1,1,1]);points=torch.tensor([-1,-1,-1,0,-1,2]);mass=torch.ones(6)
        coef,bias,diag=objective.fit_smooth_presence(x,mask,y,points,mass,normal_reduction='max_bound')
        self.assertTrue(diag['converged'])
        self.assertLessEqual(diag['max_gradient'],1e-5)
        self.assertTrue(torch.isfinite(coef).all() and torch.isfinite(bias))
        self.assertEqual((2,1),(diag['point_positive_bags'],diag['presence_positive_bags']))
        with self.assertRaises(ValueError):
            objective.smooth_presence_loss(torch.zeros(3),1,torch.ones(3,dtype=torch.bool),9,'max_bound')
