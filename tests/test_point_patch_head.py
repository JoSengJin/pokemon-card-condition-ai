import unittest
import torch
from torch.nn import functional as F
from card_condition.point_patch_head import point_bag_loss,fit_point_bag_head


class PointPatchHeadTests(unittest.TestCase):
    def test_max_bound_does_not_dilute_a_rare_normal_alarm(self):
        mask=torch.tensor([True,True,False])
        x=torch.tensor([-6.,2.,99.],requires_grad=True)
        loss=point_bag_loss(x,0,mask,normal_reduction='max_bound')
        self.assertGreaterEqual(float(loss.detach()),float(F.softplus(x[:2].max()).detach()))
        loss.backward()
        self.assertGreater(float(x.grad[1]),float(x.grad[0]))
        self.assertEqual(float(x.grad[2]),0)
        point=torch.tensor([-2.,99.],requires_grad=True)
        point_bag_loss(point,1,torch.ones(2,dtype=torch.bool),0,'max_bound').backward()
        self.assertEqual(float(point.grad[1]),0)

    def test_objective_selection_preserves_default_and_rejects_unknown(self):
        x=torch.tensor([-1.,2.]);mask=torch.ones(2,dtype=torch.bool)
        self.assertEqual(point_bag_loss(x,0,mask),point_bag_loss(x,0,mask,normal_reduction='mean_odds'))
        with self.assertRaises(ValueError):point_bag_loss(x,0,mask,normal_reduction='other')
        with self.assertRaises(ValueError):fit_point_bag_head(None,None,None,None,None,normal_reduction='other')

    def test_unknown_positive_tokens_have_no_training_gradient(self):
        x=torch.tensor([-2.,9.,-8.],requires_grad=True)
        loss=point_bag_loss(x,1,torch.tensor([True,True,True]),0);loss.backward()
        self.assertLess(float(x.grad[0]),0)
        self.assertEqual(x.grad[1:].abs().sum(),0)

    def test_normal_bag_emphasizes_rare_false_alarm_and_ignores_padding(self):
        x=torch.tensor([-5.,4.,99.],requires_grad=True);mask=torch.tensor([True,True,False])
        value=point_bag_loss(x,0,mask)
        self.assertGreater(float(value.detach()),float(F.softplus(x[:2]).mean().detach()))
        value.backward();self.assertGreater(float(x.grad[1]),float(x.grad[0]))
        self.assertEqual(float(x.grad[2]),0)

    def test_duplicating_normal_tokens_does_not_multiply_crop_mass(self):
        x=torch.tensor([-.2,1.7],dtype=torch.float64)
        a=point_bag_loss(x,0,torch.ones(2,dtype=torch.bool))
        b=point_bag_loss(x.repeat(3),0,torch.ones(6,dtype=torch.bool))
        self.assertTrue(torch.allclose(a,b,atol=1e-12))

    def test_fit_and_export_preserve_point_unknowns(self):
        x=torch.tensor([[[2.],[99.]], [[-2.],[-1.]], [[3.],[88.]], [[-3.],[-2.]]])
        masks=torch.ones(4,2,dtype=torch.bool);truth=torch.tensor([1,0,1,0]);points=torch.tensor([0,-1,0,-1]);mass=torch.ones(4)
        c,b,d=fit_point_bag_head(x,masks,truth,points,mass)
        self.assertTrue(d['converged']);self.assertLess(d['max_gradient'],1e-5)
        self.assertGreater(float((torch.tensor([2.])@c+b).sigmoid()),.5)
        self.assertLess(float((torch.tensor([-1.])@c+b).sigmoid()),.5)
        changed=x.clone();changed[truth==1,1]= -999.
        c2,b2,_=fit_point_bag_head(changed,masks,truth,points,mass)
        self.assertTrue(torch.allclose(c,c2,atol=1e-6));self.assertTrue(torch.allclose(b,b2,atol=1e-6))

    def test_missing_point_or_unconfirmed_class_is_rejected(self):
        with self.assertRaises(ValueError):point_bag_loss(torch.zeros(2),1,torch.tensor([True,False]),1)
        with self.assertRaises(ValueError):point_bag_loss(torch.zeros(2),None,torch.ones(2,dtype=torch.bool))
        with self.assertRaises(ValueError):fit_point_bag_head(torch.zeros(2,2,1),torch.ones(2,2,dtype=torch.bool),torch.zeros(2),torch.tensor([-1,-1]),torch.ones(2))


if __name__=='__main__':unittest.main()
