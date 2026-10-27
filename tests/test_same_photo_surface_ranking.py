import copy
import importlib.util
from pathlib import Path
import unittest

import torch
from card_condition.detail_bag import fit_detail_head

PATH=Path(__file__).resolve().parents[1]/'tools/experiments/surface-same-photo-ranking-20261027/objective.py'
spec=importlib.util.spec_from_file_location('same_photo_surface_ranking',PATH)
objective=importlib.util.module_from_spec(spec)
spec.loader.exec_module(objective)


def fixture():
    torch.manual_seed(11)
    x=torch.randn(6,3,2);masks=torch.ones(6,3,dtype=torch.bool)
    y=torch.tensor([0,0,0,1,1,1]);tokens=torch.tensor([-1,-1,-1,0,-1,2]);mass=torch.ones(6)
    rows=[dict(id=str(i),group='group-'+str(i),image='photo-'+str(i),side='front',target=int(y[i]),
               labels=dict(surface_defect=int(y[i])),box=[0,0,.2,.2],
               point=dict(label='surface_defect',x=.8,y=.8) if int(tokens[i])>=0 else None) for i in range(6)]
    rows[3].update(group=rows[0]['group'],image=rows[0]['image'])
    return x,masks,y,tokens,mass,rows


class SamePhotoRankingTest(unittest.TestCase):
    def test_only_explicit_same_photo_kind_pairs_and_held_groups(self):
        x,masks,y,tokens,mass,rows=fixture()
        self.assertEqual([(3,(0,))],objective.training_pairs(rows,tokens))
        changed=copy.deepcopy(rows);changed[0]['group']='other'
        self.assertEqual([],objective.training_pairs(changed,tokens))
        keep=[i for i,r in enumerate(rows) if r['group']!=rows[3]['group']]
        self.assertEqual([],objective.training_pairs([rows[i] for i in keep],tokens[keep]))
        for kind in ('wrong_kind','unknown_normal','contradiction'):
            changed=copy.deepcopy(rows)
            if kind=='wrong_kind':changed[3]['point']['label']='edge_defect'
            elif kind=='unknown_normal':changed[0]['labels']['surface_defect']=None
            else:changed[0]['box']=[.7,.7,.9,.9]
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                objective.training_pairs(changed,tokens)

    def test_ranking_gradient_raises_point_lowers_only_confirmed_normal_and_cancels_bias(self):
        logits=torch.tensor([[.3,.2,8.],[.6,.5,9.],[1.,2.,3.]],dtype=torch.float64,requires_grad=True)
        masks=torch.tensor([[True,True,False],[True,True,False],[True,True,True]])
        loss=objective.same_photo_ranking_loss(logits,masks,torch.tensor([0,-1,-1]),
                                             torch.tensor([.5,.5,0.],dtype=torch.float64),[(0,(1,))])
        loss.backward()
        self.assertLess(float(logits.grad[0,0]),0)
        self.assertTrue((logits.grad[1,:2]>0).all())
        self.assertEqual(0.,float(logits.grad[0,1:].abs().sum()+logits.grad[1,2:].abs().sum()+logits.grad[2].abs().sum()))
        self.assertAlmostEqual(0.,float(logits.grad.sum()),places=12)

    def test_no_pairs_fit_matches_original_objective(self):
        x,masks,y,tokens,mass,rows=fixture();rows[3]['image']='independent-photo'
        before=fit_detail_head(x,masks,y,tokens,mass,normal_reduction='max_bound')
        after=objective.fit_rank_head(x,masks,y,tokens,mass,rows,normal_reduction='max_bound')
        self.assertTrue(torch.allclose(before[0],after[0],atol=2e-6,rtol=0))
        self.assertTrue(torch.allclose(before[1],after[1],atol=2e-6,rtol=0))
        self.assertAlmostEqual(before[2]['train_objective'],after[2]['train_objective'],places=8)
        self.assertEqual(0,after[2]['ranking_point_pairs'])

    def test_rank_fit_converges_without_changing_original_mass(self):
        x,masks,y,tokens,mass,rows=fixture();old=mass.clone()
        coef,bias,diag=objective.fit_rank_head(x,masks,y,tokens,mass,rows,normal_reduction='max_bound')
        self.assertTrue(diag['converged'])
        self.assertLessEqual(diag['max_gradient'],1e-5)
        self.assertTrue(torch.equal(old,mass))
        self.assertEqual((1,1),(diag['ranking_point_pairs'],diag['ranking_comparisons']))
        self.assertTrue(torch.isfinite(coef).all() and torch.isfinite(bias))
