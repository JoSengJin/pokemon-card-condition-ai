import unittest
import torch
from card_condition.observation_ridge import fit_side_ridge
from card_condition.visibility_model import TARGET


class ObservationRidgeTest(unittest.TestCase):
    def test_fixed_regularizer_and_unpenalized_intercept(self):
        rows=[dict(side=side,group=f'{side}-{label}',labels={TARGET:label})
              for side in ('front','back') for label in (0,1)]
        features=torch.tensor([[-1.],[1.],[9.],[11.]])
        head=torch.nn.Linear(1,2)
        fit_side_ridge(head,features,rows)
        torch.testing.assert_close(head.weight,torch.tensor([[.5],[.5]]),rtol=0,atol=1e-6)
        torch.testing.assert_close(head.bias,torch.tensor([0.,-5.]),rtol=0,atol=1e-6)
        with self.assertRaisesRegex(ValueError,'Invalid'):
            fit_side_ridge(head,torch.tensor([[float('inf')],[1.],[9.],[11.]]),rows)
        with self.assertRaisesRegex(ValueError,'Both observation'):
            fit_side_ridge(head,features[[0,2]], [rows[0],rows[2]])
