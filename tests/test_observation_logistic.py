import unittest
from unittest.mock import patch
import torch
from card_condition.observation_logistic import fit_side_logistic
from card_condition.visibility_model import TARGET


class ObservationLogisticTest(unittest.TestCase):
    def test_convex_stationarity_bias_and_no_gradient_leak_to_features(self):
        rows=[dict(side=s,group=f'{s}-{y}',labels={TARGET:y}) for s in ('front','back') for y in (0,1)]
        x=torch.tensor([[-1.],[1.],[9.],[11.]],requires_grad=True)
        h=torch.nn.Linear(1,2)
        with torch.no_grad():diagnostics=fit_side_logistic(h,x,rows)
        # Symmetry: unpenalized bias centers the classifier at each side's midpoint.
        self.assertAlmostEqual(0.,h.bias[0].item(),places=5)
        self.assertAlmostEqual(-10*h.weight[1].item(),h.bias[1].item(),places=5)
        self.assertAlmostEqual(h.weight[0].item(),h.weight[1].item(),places=5)
        w=h.weight[0].item()
        self.assertGreater(w,0)
        self.assertAlmostEqual(torch.sigmoid(torch.tensor(w)).item()-1+2*w,0.,places=5)
        self.assertIsNone(x.grad)
        shifted=torch.nn.Linear(1,2)
        fit_side_logistic(shifted,x.detach()+1000,rows)
        torch.testing.assert_close(shifted.weight,h.weight,rtol=0,atol=1e-6)
        torch.testing.assert_close(shifted.bias+1000*shifted.weight[:,0],h.bias,rtol=0,atol=1e-4)
        self.assertTrue(all(d['gradient_max']<=1e-6 for d in diagnostics))
        with self.assertRaisesRegex(ValueError,'Invalid'):
            fit_side_logistic(h,x.detach()*float('inf'),rows)
        with self.assertRaisesRegex(ValueError,'Both observation'):
            fit_side_logistic(h,x[[0,2]], [rows[0],rows[2]])
        with patch('torch.optim.LBFGS.step',return_value=None):
            with self.assertRaisesRegex(ValueError,'did not converge'):
                fit_side_logistic(h,x,rows)
