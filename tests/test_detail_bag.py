import unittest
import torch
from card_condition.detail_bag import detail_bag_loss
from card_condition.point_patch_head import point_bag_loss

class DetailBagLossTest(unittest.TestCase):
    def test_max_bound_preserves_point_and_presence_supervision(self):
        mask=torch.tensor([True,True,False]);x=torch.tensor([-2.,3.,99.],requires_grad=True)
        self.assertEqual(detail_bag_loss(x,0,mask,normal_reduction='max_bound'),point_bag_loss(x,0,mask,normal_reduction='max_bound'))
        detail_bag_loss(x,1,mask,normal_reduction='max_bound').backward()
        self.assertEqual(float(x.grad[0]),0);self.assertEqual(float(x.grad[2]),0)
        self.assertLess(float(x.grad[1]),0)
        self.assertEqual(detail_bag_loss(x,1,mask,0,'max_bound'),point_bag_loss(x,1,mask,0,'max_bound'))

    def test_all_point_max_bound_fit_matches_point_fitter(self):
        from card_condition.detail_bag import fit_detail_head
        from card_condition.point_patch_head import fit_point_bag_head
        x=torch.tensor([[[2.],[99.]],[[-2.],[-1.]],[[3.],[88.]],[[-3.],[-2.]]])
        masks=torch.ones(4,2,dtype=torch.bool);y=torch.tensor([1,0,1,0]);points=torch.tensor([0,-1,0,-1]);mass=torch.ones(4)
        c,b,_=fit_detail_head(x,masks,y,points,mass,normal_reduction='max_bound')
        c2,b2,_=fit_point_bag_head(x,masks,y,points,mass,normal_reduction='max_bound')
        self.assertTrue(torch.allclose(c,c2,atol=1e-6));self.assertTrue(torch.allclose(b,b2,atol=1e-6))
        with self.assertRaises(ValueError):fit_detail_head(None,None,None,None,None,normal_reduction='unknown')

    def test_presence_never_requires_a_fabricated_point(self):
        x=torch.tensor([-2.,3.,99.],requires_grad=True);mask=torch.tensor([True,True,False])
        detail_bag_loss(x,1,mask).backward()
        self.assertEqual(float(x.grad[0]),0);self.assertLess(float(x.grad[1]),0);self.assertEqual(float(x.grad[2]),0)

    def test_exact_human_point_keeps_original_point_semantics(self):
        x=torch.tensor([-2.,3.],requires_grad=True);mask=torch.ones(2,dtype=torch.bool)
        self.assertEqual(detail_bag_loss(x,1,mask,0),point_bag_loss(x,1,mask,0))
        detail_bag_loss(x,1,mask,0).backward();self.assertLess(float(x.grad[0]),0);self.assertEqual(float(x.grad[1]),0)

    def test_normal_presence_uses_existing_normal_bag_loss(self):
        x=torch.tensor([-2.,3.]);mask=torch.ones(2,dtype=torch.bool)
        self.assertEqual(detail_bag_loss(x,0,mask),point_bag_loss(x,0,mask))

    def test_unknown_truth_padding_and_invalid_points_rejected(self):
        for target,mask,point in [(None,torch.ones(2,dtype=torch.bool),None),(True,torch.ones(2,dtype=torch.bool),None),(1,torch.zeros(2,dtype=torch.bool),None),(1,torch.tensor([True,False]),1)]:
            with self.assertRaises(ValueError):detail_bag_loss(torch.zeros(2),target,mask,point)

    def test_presence_is_not_changed_by_duplicate_tokens(self):
        x=torch.tensor([-.5,2.]);mask=torch.ones(2,dtype=torch.bool)
        self.assertEqual(detail_bag_loss(x,1,mask),detail_bag_loss(x.repeat(3),1,mask.repeat(3)))

    def test_mixed_supervision_fit_converges_without_relabelling_unknowns(self):
        from card_condition.detail_bag import fit_detail_head
        x=torch.tensor([[[2.],[99.]],[[3.],[0.]],[[-2.],[-1.]],[[-3.],[-2.]]])
        masks=torch.ones(4,2,dtype=torch.bool);y=torch.tensor([1,1,0,0]);points=torch.tensor([0,-1,-1,-1]);mass=torch.ones(4)
        c,b,d=fit_detail_head(x,masks,y,points,mass)
        self.assertTrue(d['converged']);self.assertEqual(d['point_positive_bags'],1);self.assertEqual(d['presence_positive_bags'],1)
        self.assertGreater(float((torch.tensor([2.])@c+b).sigmoid()),.5)
        self.assertLess(float((torch.tensor([-1.])@c+b).sigmoid()),.5)
        changed=x.clone();changed[0,1]=-999.
        c2,b2,_=fit_detail_head(changed,masks,y,points,mass)
        self.assertTrue(torch.allclose(c,c2,atol=1e-5));self.assertTrue(torch.allclose(b,b2,atol=1e-5))

    def test_positive_only_and_missing_normal_mass_cannot_start_fit(self):
        from card_condition.detail_bag import fit_detail_head
        x=torch.ones(2,2,1);masks=torch.ones(2,2,dtype=torch.bool);points=torch.tensor([0,-1])
        with self.assertRaisesRegex(ValueError,'Both confirmed human classes'):
            fit_detail_head(x,masks,torch.ones(2,dtype=torch.long),points,torch.ones(2))
        with self.assertRaisesRegex(ValueError,'Both confirmed human classes'):
            fit_detail_head(x,masks,torch.tensor([1,0]),points,torch.tensor([1.,0.]))
