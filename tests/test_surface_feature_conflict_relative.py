import importlib.util
from pathlib import Path
import unittest
import torch
root=Path(__file__).resolve().parents[1]
modules={}
for name,path in [('analysis','tools/experiments/surface-feature-conflict-relative-20261028/analysis.py'),('transform','tools/experiments/surface-feature-conflict-relative-20261028/transform.py'),('multi','tools/experiments/surface-all-human-points-20261028/objective.py')]:
    spec=importlib.util.spec_from_file_location(name,root/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);modules[name]=m

class SurfaceFeatureConflictRelativeTests(unittest.TestCase):
    def test_relative_translation_invariant_valid_only_and_local(self):
        x=torch.tensor([[[2.,4.],[4.,8.],[900.,999.]],[[3.,-1.],[5.,1.],[7.,0.]]],dtype=torch.float64)
        mask=torch.tensor([[True,True,False],[True,True,True]])
        actual=modules['transform'].relative_tokens(x,mask)
        for i in range(2):torch.testing.assert_close(actual[i,mask[i]].mean(0),torch.zeros(2,dtype=torch.float64))
        self.assertTrue(torch.equal(actual[0,2],x[0,2]))
        shifted=x.clone();shifted[0,mask[0]]+=torch.tensor([100.,-53.]);shifted[0,2]=0
        translated=modules['transform'].relative_tokens(shifted,mask)
        torch.testing.assert_close(actual[0,mask[0]],translated[0,mask[0]]);self.assertTrue(torch.equal(actual[1],translated[1]))
        with self.assertRaises(ValueError):modules['transform'].relative_tokens(x,torch.zeros_like(mask))

    def test_common_residual_peak_decomposition(self):
        x=torch.tensor([[4.,1.],[1.,6.],[99.,99.]],dtype=torch.float64);mask=torch.tensor([True,True,False])
        result=modules['analysis'].components(x,mask,torch.tensor([1.,0.]),.3,torch.tensor([0.,1.]),-.1)
        self.assertLess(result['additive_error'],1e-8);self.assertEqual(result['old_peak'],0);self.assertEqual(result['new_peak'],1)
        self.assertAlmostEqual(result['delta_logit'],result['common_delta']+result['residual_delta']+result['peak_relocation'])

    def test_split_gradient_matches_directional_finite_difference(self):
        x=torch.tensor([[[1.,0.],[0.,1.],[2.,0.]],[[2.,1.],[1.,0.],[0.,1.]],[[-1.,0.],[0.,-1.],[-1.,-1.]]],dtype=torch.float64)
        mask=torch.ones((3,3),dtype=torch.bool);first=torch.tensor([0,-1,-1]);mass=dict(weights=torch.tensor([.3,.3,.4]),targets=[1,1,0]);center=torch.zeros(2,dtype=torch.float64);w=torch.tensor([.2,-.1],dtype=torch.float64);points=[[0,1],[],[]]
        d,g=modules['analysis'].gradients(x,mask,first,mass,center,w,-.3,points,True,modules['multi'].all_point_loss)
        self.assertLess(d['sum_error'],1e-10)
        direction=torch.tensor([.4,-.7,.2],dtype=torch.float64);values=[];eps=1e-5
        for sign in (-1,1):
            info,_=modules['analysis'].gradients(x,mask,first,mass,center,w+sign*eps*direction[:2],-.3+sign*eps*float(direction[2]),points,True,modules['multi'].all_point_loss)
            values.append(sum(info['losses'].values()))
        self.assertAlmostEqual((values[1]-values[0])/(2*eps),float(sum(g.values())@direction),places=7)
        original,_=modules['analysis'].gradients(x,mask,first,mass,center,w,-.3,points,False,modules['multi'].all_point_loss)
        self.assertNotEqual(original['losses']['point'],d['losses']['point'])

    def test_neighbor_pools_use_explicit_points_and_normals(self):
        x=torch.tensor([[[1.,0.],[0.,1.]],[[-1.,0.],[0.,-1.]]]);mask=torch.ones(2,2,dtype=torch.bool)
        rows=[dict(id='p',group='train-p',target=1),dict(id='n',group='train-n',target=0)]
        result=modules['analysis'].neighbors(x,mask,rows,[[0],[]],torch.tensor([1.,0.]))
        self.assertEqual(1,result['human_points']['pool_tokens']);self.assertEqual('p',result['human_points']['top'][0]['id']);self.assertAlmostEqual(1.,result['human_points']['top'][0]['cosine'])
        self.assertEqual(2,result['explicit_normal_tokens']['pool_tokens']);self.assertEqual({'train-n'},{v['group'] for v in result['explicit_normal_tokens']['top']})
