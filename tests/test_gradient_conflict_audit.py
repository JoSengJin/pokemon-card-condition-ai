"""Synthetic autograd/finite-difference checks; no model fitting or provider calls."""
import importlib.util
from pathlib import Path
import unittest
import torch
spec=importlib.util.spec_from_file_location('gradient_audit_worker',Path(__file__).resolve().parents[1]/'artifacts/fixed67-gradient-conflict-20261021/worker.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class GradientAuditTest(unittest.TestCase):
 def test_projection_sign_exact_point_and_unchanged_frozen_parameters(self):
  x=torch.tensor([[[1.,0.],[0.,1.]],[[2.,0.],[0.,2.]]],dtype=torch.float64)
  mask=torch.ones((2,2),dtype=torch.bool);points=torch.tensor([-1,0]);mass=torch.tensor([.25,.25],dtype=torch.float64)
  w=torch.zeros(2,dtype=torch.float64,requires_grad=True);b=torch.zeros((),dtype=torch.float64,requires_grad=True)
  queries=[dict(id='D',kind='actual_point',vector=torch.tensor([1.,0.],dtype=torch.float64)),dict(id='FP',kind='false_positive',vector=torch.tensor([0.,1.],dtype=torch.float64))]
  saved=[v.detach().clone() for v in (x,w,b)]
  result,error=audit.projections(x,mask,points,mass,w,b,{'normal-bag':[0],'normal-point':[1]},queries)
  exact=next(v for v in result if v['group']=='normal-point')['projections']
  self.assertAlmostEqual(exact[0]['unit_descent_logit_change'],-.375,places=10)
  self.assertAlmostEqual(exact[1]['unit_descent_logit_change'],-.125,places=10)
  self.assertLess(error,1e-6)
  self.assertTrue(all(torch.equal(before,after.detach()) for before,after in zip(saved,(x,w,b))))
  self.assertIsNone(w.grad);self.assertIsNone(b.grad)
 def test_large_feature_direction_is_normalized_for_numerical_check_only(self):
  x=torch.tensor([[[100.,0.],[0.,100.]]],dtype=torch.float64)
  mask=torch.ones((1,2),dtype=torch.bool);points=torch.tensor([-1]);mass=torch.tensor([.25],dtype=torch.float64)
  w=torch.tensor([.005,.004],dtype=torch.float64,requires_grad=True);b=torch.zeros((),dtype=torch.float64,requires_grad=True)
  q=torch.tensor([100.,0.],dtype=torch.float64)
  loss=mass[0]*audit.normal_loss(x[0]@w+b,mask[0],-1);gw,gb=torch.autograd.grad(loss,(w,b));expected=-float(q@gw+gb)
  result,error=audit.projections(x,mask,points,mass,w,b,{'normal':[0]},[dict(id='D',kind='actual_point',vector=q)])
  self.assertAlmostEqual(result[0]['projections'][0]['unit_descent_logit_change'],expected,places=8)
  self.assertLess(error,1e-3)
if __name__=='__main__':unittest.main()
