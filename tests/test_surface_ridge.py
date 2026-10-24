import unittest
import torch
from card_condition.surface_ridge import fit_ridge


class SurfaceRidgeTest(unittest.TestCase):
    def test_known_centered_solution_and_unpenalized_intercept(self):
        w,b=fit_ridge([[9.],[11.]],[0,1],[1,1])
        self.assertAlmostEqual(w.item(),.5,places=6)
        self.assertAlmostEqual(b.item(),-5.,places=6)

    def test_zero_weight_validation_features_and_labels_cannot_affect_fit(self):
        expected=fit_ridge([[0.,2.],[2.,3.]],[0,1],[1,1])
        actual=fit_ridge([[0.,2.],[2.,3.],[float('nan'),float('inf')]],[0,1,float('nan')],[1,1,0])
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(expected,actual)))

    def test_duplicate_patches_do_not_add_physical_group_weight(self):
        a=fit_ridge([[0.],[2.]],[0,1],[1,1]);b=fit_ridge([[0.],[0.],[2.]],[0,0,1],[.5,.5,1])
        self.assertTrue(all(torch.allclose(x,y,atol=1e-7) for x,y in zip(a,b)))

    def test_invalid_inputs_rejected(self):
        for labels,weights in [([0,0],[1,1]),([0,1],[0,0]),([0,1],[1,-1]),([0,2],[1,1]),([0,1],[1,float('nan')])]:
            with self.assertRaises(ValueError):fit_ridge([[0.],[2.]],labels,weights)
        for penalty in [0,-1,True,float('nan')]:
            with self.assertRaises(ValueError):fit_ridge([[0.],[2.]],[0,1],[1,1],penalty)

    def test_float32_checkpoint_overflow_is_rejected(self):
        x=torch.tensor([[-1e-45],[1e-45]],dtype=torch.float64)
        with self.assertRaisesRegex(ValueError,'Non-finite'):
            fit_ridge(x,[0,1],[1,1],1e-100)
