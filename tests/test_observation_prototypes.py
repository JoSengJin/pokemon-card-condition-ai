import copy
import unittest
import torch
from card_condition.observation_prototypes import prototype_scores

TARGET='observation_limited'


class PrototypeTest(unittest.TestCase):
    def fixture(self):
        rows=[dict(group=str(i),split='train',labels={TARGET:t}) for i,t in enumerate([0,0,1,1])]
        return torch.tensor([[0.,0.],[2.,0.],[8.,0.],[10.,0.]]),rows

    def test_nearest_distance_and_query_truth_independence(self):
        x,rows=self.fixture();q=torch.tensor([[9.,0.],[1.,0.]])
        query=[dict(group='a',labels={TARGET:0}),dict(group='b',labels={TARGET:1})]
        scores=prototype_scores(x,rows,q,query)
        expected=torch.sigmoid(torch.tensor([24.,-24.]))
        self.assertTrue(torch.equal(scores,expected))
        query[0]['labels']='not read';query[1]['labels']=None
        self.assertTrue(torch.equal(scores,prototype_scores(x,rows,q,query)))
        self.assertTrue(torch.equal(scores,prototype_scores(torch.cat([x,x[:1]]),rows+[rows[0]],q,query)))

    def test_overlap_and_nontraining_truth_are_rejected(self):
        x,rows=self.fixture();q=x[:1]
        with self.assertRaisesRegex(ValueError,'excluded'):
            prototype_scores(x,rows,q,[dict(group='0')])
        for split in ('val','test',None):
            changed=copy.deepcopy(rows);changed[0]['split']=split
            with self.assertRaisesRegex(ValueError,'training-only'):
                prototype_scores(x,changed,q,[dict(group='new')])
        changed=copy.deepcopy(rows)
        for r in changed:r['labels'][TARGET]=0
        with self.assertRaisesRegex(ValueError,'Both explicit'):
            prototype_scores(x,changed,q,[dict(group='new')])

    def test_invalid_features_fail_instead_of_returning_scores(self):
        x,rows=self.fixture()
        for bad in (torch.full_like(x,float('nan')),torch.zeros(4,0),x.long()):
            with self.subTest(shape=bad.shape),self.assertRaises(ValueError):
                prototype_scores(bad,rows,torch.zeros(1,bad.shape[1]),[dict(group='new')])
        with self.assertRaisesRegex(ValueError,'Non-finite'):
            prototype_scores(x*1e30,rows,torch.ones(1,2)*1e30,[dict(group='new')])
