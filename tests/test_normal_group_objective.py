import importlib.util
from pathlib import Path
import unittest

import torch
from card_condition.detail_bag import fit_detail_head

PATH=Path(__file__).resolve().parents[1]/'tools/experiments/surface-normal-group-objective-20261027/objective.py'
spec=importlib.util.spec_from_file_location('normal_group_objective',PATH)
objective=importlib.util.module_from_spec(spec)
spec.loader.exec_module(objective)


class NormalGroupObjectiveTest(unittest.TestCase):
    def test_one_normal_group_is_original_objective(self):
        torch.manual_seed(11)
        x=torch.randn(6,3,2); masks=torch.ones(6,3,dtype=torch.bool)
        y=torch.tensor([0,0,0,1,1,1]);points=torch.tensor([-1,-1,-1,0,-1,2])
        mass=torch.ones(6)
        old=fit_detail_head(x,masks,y,points,mass,normal_reduction='max_bound')
        new=objective.fit_normal_group_head(x,masks,y,points,mass,['normal']*3+['p1','p2','p3'])
        self.assertTrue(torch.allclose(old[0],new[0],atol=2e-6,rtol=0))
        self.assertTrue(torch.allclose(old[1],new[1],atol=2e-6,rtol=0))
        self.assertAlmostEqual(old[2]['train_objective'],new[2]['train_objective'],places=8)
        self.assertTrue(new[2]['converged'])

    def test_unequal_normal_group_mass_preserved_and_finite(self):
        torch.manual_seed(12)
        x=torch.randn(6,3,2); masks=torch.ones(6,3,dtype=torch.bool)
        y=torch.tensor([0,0,0,1,1,1]);points=torch.tensor([-1,-1,-1,0,-1,2])
        old=fit_detail_head(x,masks,y,points,torch.ones(6),normal_reduction='max_bound')
        new=objective.fit_normal_group_head(x,masks,y,points,torch.ones(6),['n1','n1','n2','p1','p2','p3'])
        self.assertTrue(new[2]['converged'])
        self.assertTrue(torch.isfinite(new[0]).all() and torch.isfinite(new[1]))
        self.assertGreaterEqual(new[2]['train_objective'],old[2]['train_objective']-1e-8)
        self.assertEqual((2,1),(new[2]['point_positive_bags'],new[2]['presence_positive_bags']))

    def test_missing_groups_zero_mass_and_changed_class_balance_rejected(self):
        x=torch.zeros(2,2,1);mask=torch.ones(2,2,dtype=torch.bool)
        y=torch.tensor([0,1]);points=torch.tensor([-1,0])
        for mass,groups in (([1,1],['n']),([1,1],['n','']),([0,1],['n','p']),([1,2],['n','p'])):
            with self.subTest(mass=mass,groups=groups),self.assertRaises(ValueError):
                objective.fit_normal_group_head(x,mask,y,points,torch.tensor(mass),groups)
