import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import torch
root=Path(__file__).resolve().parents[1];modules={}
for name in ('features','nonlinear','worker','audit'):
    spec=importlib.util.spec_from_file_location(name,root/'tools/experiments/surface-preserved-heads-20261028'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);modules[name]=m

class SurfacePreservedHeadsTests(unittest.TestCase):
    def test_original_linear_model_is_embedded_and_padding_unchanged(self):
        x=torch.tensor([[[1.,2.],[3.,4.],[50.,60.]],[[2.,1.],[6.,2.],[4.,6.]]],dtype=torch.float64);original=x.clone();mask=torch.tensor([[True,True,False],[True,True,True]])
        expanded=modules['features'].preserved_features(x,mask)
        self.assertTrue(torch.equal(x,original));self.assertTrue(torch.equal(expanded[:,:,:2],x));self.assertTrue(torch.equal(expanded[0,2,2:],torch.zeros(2,dtype=x.dtype)))
        w=torch.tensor([.2,-.7],dtype=torch.float64)
        torch.testing.assert_close(expanded@torch.cat((w,torch.zeros_like(w)))+.3,x@w+.3,atol=1e-12,rtol=0)

    def test_residual_is_local_and_translation_invariant(self):
        x=torch.arange(12,dtype=torch.float64).reshape(2,3,2);mask=torch.ones((2,3),dtype=torch.bool);before=modules['features'].preserved_features(x,mask)
        changed=x.clone();changed[0]+=torch.tensor([23.,-7.]);after=modules['features'].preserved_features(changed,mask)
        self.assertTrue(torch.equal(before[1],after[1]));torch.testing.assert_close(before[0,:,2:],after[0,:,2:]);torch.testing.assert_close(before[:,:,2:].mean(1),torch.zeros((2,2),dtype=x.dtype))

    def test_separated_roles_preserve_weak_truth_and_average_raw_logits(self):
        rows=[dict(id=str(i),group=str(i),target=v) for i,v in enumerate([1,1,0,0,1])];ctx=dict(all_rows=rows,x=torch.ones(5,2,1),masks=torch.ones((5,2),dtype=torch.bool),tokens=torch.tensor([0,-1,-1,-1,0]));f=modules['worker']
        with patch.object(f,'fit_detail_head',side_effect=[(torch.tensor([1.]),torch.tensor(.2),dict(max_gradient=0.)),(torch.tensor([3.]),torch.tensor(-.4),dict(max_gradient=0.))]) as fit:
            maps,head,diag=f.fit_fold(ctx,[0,1,2,3],[4],'separated',None,None)
        self.assertEqual(['0','2','3'],head['point_train_ids']);self.assertEqual([1,0,0],fit.call_args_list[0].args[2].tolist());self.assertEqual([1,1,0,0],fit.call_args_list[1].args[2].tolist());self.assertEqual([-1]*4,fit.call_args_list[1].args[3].tolist());self.assertEqual(1,ctx['all_rows'][1]['target'])
        torch.testing.assert_close(maps,torch.full((1,2),1.9).sigmoid());self.assertEqual('fixed_half_raw_logits',diag['combination'])

    def test_tiny_nonlinear_fit_initialization_and_saved_forward(self):
        torch.set_num_threads(1);m=modules['nonlinear'];x=torch.tensor([[[-2.],[-1.]],[[1.],[2.]]]);mask=torch.ones((2,2),dtype=torch.bool)
        state,diag=m.fit_nonlinear(x,mask,torch.tensor([0,1]),torch.tensor([-1,0]),torch.ones(2))
        self.assertEqual(0.,diag['initial_logit_max']);self.assertEqual(8,diag['hidden_units']);self.assertLessEqual(diag['max_gradient'],1e-5)
        logits=m.nonlinear_logits(x,state);copy={k:v.clone() for k,v in state.items()};self.assertTrue(torch.equal(logits,m.nonlinear_logits(x,copy)));self.assertTrue(torch.isfinite(logits).all());self.assertTrue(all(not v.requires_grad for v in state.values()))


    def test_nonlinear_float64_prediction_is_stored_in_float32_map(self):
        f=modules['worker'];n=modules['nonlinear'];ctx=dict(all_rows=[dict(id=str(i),group=str(i),target=v) for i,v in enumerate([0,1,1])],x=torch.ones(3,2,1),masks=torch.ones((3,2),dtype=torch.bool),tokens=torch.tensor([-1,0,0]))
        with patch.object(n,'fit_nonlinear',return_value=({},dict(converged=True,max_gradient=0.))),patch.object(n,'nonlinear_logits',return_value=torch.tensor([[.1,.2]],dtype=torch.float64)):
            values,head,diag=f.fit_fold(ctx,[0,1],[2],'nonlinear',None,n)
        self.assertEqual(torch.float32,values.dtype);maps=torch.zeros(3,2,dtype=torch.float32);maps[[2]]=values
        torch.testing.assert_close(maps[2],torch.tensor([.1,.2],dtype=torch.float64).sigmoid().float());self.assertEqual(torch.float32,maps.dtype)


    def test_audit_counts_keep_point_and_weak_denominators_distinct(self):
        rows=[dict(target=1),dict(target=1),dict(target=0)];first=torch.tensor([0,-1,-1]);maps=torch.tensor([[.2,.8],[.4,.3],[.7,.1]]);mask=torch.ones((3,2),dtype=torch.bool)
        value=modules['audit'].counts(rows,first,maps,mask)
        self.assertEqual(dict(fn=1,positives=2,fp=1,negatives=1,point_fn=1,points=1,weak_fn=1,weak_positives=1),value)

    def test_original_objective_is_preserved_by_zero_residual_weights(self):
        x=torch.tensor([[[2.,1.],[1.,0.]],[[-1.,0.],[0.,-1.]]]);mask=torch.ones((2,2),dtype=torch.bool);first=torch.tensor([0,-1]);rows=[dict(target=1),dict(target=0)];mass=torch.ones(2);w=torch.tensor([.2,-.4]);f=modules['features'].preserved_features(x,mask)
        a=modules['audit'].objective(x,mask,first,rows,mass,w,.1);b=modules['audit'].objective(f,mask,first,rows,mass,torch.cat((w,torch.zeros_like(w))),.1)
        self.assertAlmostEqual(a,b,places=10)
