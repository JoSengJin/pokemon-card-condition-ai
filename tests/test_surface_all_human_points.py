import importlib.util
from pathlib import Path
import unittest
import torch
from card_condition.detail_bag import fit_detail_head,detail_bag_loss

spec=importlib.util.spec_from_file_location('all_points',Path(__file__).resolve().parents[1]/'tools/experiments/surface-all-human-points-20261028/objective.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AllExistingPointTests(unittest.TestCase):
    def test_one_point_and_weak_bags_match_original_fit(self):
        x=torch.tensor([[[1.,.2],[.2,-.3]],[[-1.,.2],[-.4,.6]],[[.5,.8],[.1,.2]]])
        mask=torch.ones((3,2),dtype=torch.bool);y=torch.tensor([1,0,1]);first=torch.tensor([0,-1,-1]);mass=torch.ones(3)
        original=fit_detail_head(x,mask,y,first,mass,normal_reduction='max_bound')
        candidate=m.fit_all_point_head(x,mask,y,first,mass,[[0],[],[]],normal_reduction='max_bound')
        self.assertTrue(torch.equal(original[0],candidate[0]));self.assertTrue(torch.equal(original[1],candidate[1]))
        self.assertEqual(original[2]['train_objective'],candidate[2]['train_objective'])

    def test_average_distinct_click_tokens_and_gradients(self):
        z=torch.tensor([-1.,2.,8.],dtype=torch.float64,requires_grad=True);mask=torch.ones(3,dtype=torch.bool)
        actual=m.all_point_loss(z,1,mask,[1,0,1]);expected=torch.nn.functional.softplus(-z[:2]).mean()
        torch.testing.assert_close(actual,expected);actual.backward()
        torch.testing.assert_close(z.grad[:2],-torch.sigmoid(-z[:2].detach())/2);self.assertEqual(float(z.grad[2]),0.)
        self.assertEqual(float(m.all_point_loss(z,0,mask,[]).detach()),float(detail_bag_loss(z,0,mask,None,'max_bound').detach()))

    def test_missing_first_point_or_invalid_tokens_rejected(self):
        mask=torch.tensor([True,False]);z=torch.ones(2)
        for tokens in ([1],[2],[-1],[True]):
            with self.assertRaises(ValueError):m.all_point_loss(z,1,mask,tokens)
        with self.assertRaises(ValueError):m.all_point_loss(z,0,mask,[0])
        with self.assertRaisesRegex(ValueError,'first human'):
            m.fit_all_point_head(torch.ones(2,2,1),torch.ones(2,2,dtype=torch.bool),torch.tensor([1,0]),torch.tensor([0,-1]),torch.ones(2),[[1],[]])
