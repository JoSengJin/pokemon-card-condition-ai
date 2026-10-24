import unittest
import torch
from card_condition.surface_logistic import fit_logistic

class SurfaceLogisticTest(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_stationary_solution_and_unpenalized_intercept(self):
        w,b,info=fit_logistic([[9.],[11.]],[0,1],[1,1])
        self.assertLess(abs(w.item()-torch.sigmoid(-w).item()),1e-5)
        self.assertAlmostEqual(b.item(),-10*w.item(),places=5)
        self.assertLess(info['max_gradient'],1e-5)

    def test_held_out_nan_features_and_labels_cannot_affect_fit(self):
        a=fit_logistic([[0.,2.],[2.,3.]],[0,1],[1,1])
        b=fit_logistic([[0.,2.],[2.,3.],[float('nan'),float('inf')]],[0,1,float('nan')],[1,1,0])
        self.assertTrue(all(torch.equal(x,y) for x,y in zip(a[:2],b[:2])))
        self.assertEqual(a[2],b[2])

    def test_seed_independence_and_group_duplicate_mass(self):
        torch.manual_seed(42);a=fit_logistic([[0.],[2.]],[0,1],[1,1])
        torch.manual_seed(7);b=fit_logistic([[0.],[0.],[2.]],[0,0,1],[.5,.5,1])
        self.assertTrue(all(torch.allclose(x,y,atol=1e-6) for x,y in zip(a[:2],b[:2])))

    def test_invalid_training_rejected(self):
        for labels,weights in [([0,0],[1,1]),([0,1],[0,0]),([0,1],[1,-1]),([0,2],[1,1]),([0,1],[1,float('nan')])]:
            with self.assertRaises(ValueError):fit_logistic([[0.],[2.]],labels,weights)
        for penalty in [0,-1,True,float('nan')]:
            with self.assertRaises(ValueError):fit_logistic([[0.],[2.]],[0,1],[1,1],penalty)
