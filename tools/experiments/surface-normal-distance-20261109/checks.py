"""Synthetic normal moments, held-fold isolation, representation and385D fit."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import torch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from features import fit_normal_distribution, append_normal_distance


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261109)
    x=torch.full((3,4,384),99.);x[0,0]=1.;x[0,1]=3.;x[1,0]=5.
    mask=torch.tensor([[1,1,0,0],[1,0,0,0],[1,1,1,1]],dtype=torch.bool)
    y=torch.tensor([0,0,1]);weights=torch.tensor([1.,3.,100.])
    mean,var=fit_normal_distribution(x,mask,y,weights)
    assert torch.equal(mean,torch.full_like(mean,4.25))
    assert torch.equal(var,torch.full_like(var,1.9375))
    altered=x.clone();altered[y==1]=-1e6;altered[~mask]=1e6
    a,b=fit_normal_distribution(altered,mask,y,weights)
    assert torch.equal(a,mean) and torch.equal(b,var)
    # Evaluation data is transformed with frozen moments, never passed to fit.
    held=torch.randn(2,4,384);heldmask=torch.ones(2,4,dtype=torch.bool)
    frozen=(mean.clone(),var.clone())
    first=append_normal_distance(held,heldmask,mean,var)
    changed=append_normal_distance(held+1e4,heldmask,mean,var)
    assert not torch.equal(first,changed) and torch.equal(mean,frozen[0]) and torch.equal(var,frozen[1])
    actual=append_normal_distance(x,mask,mean,var)
    expected=torch.sqrt(((x.double()-4.25).square()/1.9375).mean(2)).float().masked_fill(~mask,0)
    assert torch.equal(actual[:,:,:384],x) and torch.equal(actual[:,:,384],expected)
    assert torch.equal(mask,torch.tensor([[1,1,0,0],[1,0,0,0],[1,1,1,1]],dtype=torch.bool))
    constant=torch.ones(1,1,384);one_mask=torch.ones(1,1,dtype=torch.bool)
    cm,cv=fit_normal_distribution(constant,one_mask,torch.tensor([0]),torch.ones(1))
    assert (cv==1e-6).all() and (append_normal_distance(constant,one_mask,cm,cv)[:,:,384]==0).all()
    for args in [(x,mask,torch.ones_like(y),weights),(x,torch.zeros_like(mask),y,weights),(x,mask,y,weights*0),(x*float('nan'),mask,y,weights),(x,mask,y.float(),weights)]:
        try:fit_normal_distribution(*args)
        except ValueError:pass
        else:raise AssertionError('Invalid training inputs accepted')
    print('PASS: hand normal moments4.25/1.9375, positive/padding invariance, held mutation/frozen statistics, exact radius, original preservation, floor/singleton/invalid rejection')
    # Worker provenance must select outer training rows before normal fitting.
    source=(HERE/'worker.py').read_text()
    assert 'train_x, train_m = x[tr], m[tr]' in source
    assert 'fit_normal_distribution(train_x,train_m,targets,mass)' in source
    assert source.index('check_separation(')<source.index('fit_normal_distribution(train_x')
    assert 'held_x = append_normal_distance(x[ho],m[ho],mean,variance)' in source
    folder=ROOT/'tools/experiments/surface-local-contrast-20261109'
    sys.path.insert(0,str(ROOT/'tools/experiments/surface-global-lme-only-20261109'))
    sys.path.insert(0,str(folder))
    dense=load('dense_alpha0',ROOT/'tools/experiments/surface-global-lme-only-20261109/objective.py')
    chunked=load('chunked_alpha0',folder/'objective.py')
    xx=torch.randn(10,3,384);valid=torch.ones(10,3,dtype=torch.bool);target=torch.tensor([0,1]*5);pt=torch.full((10,),-1);mass=torch.full((10,),.1,dtype=torch.float64)
    mu,variance=fit_normal_distribution(xx,valid,target,mass)
    augmented=append_normal_distance(xx,valid,mu,variance)
    theta=torch.randn(385,dtype=torch.float64)*.01
    expanded=torch.cat((theta[:-1],torch.zeros(1,dtype=torch.float64),theta[-1:]))
    old=dense.loss_and_grad(theta,xx.double(),valid,target,pt,mass,1.,'max_bound')
    new=chunked.loss_and_grad(expanded,augmented,valid,target,pt,mass,1.,'max_bound',torch.zeros(385,dtype=torch.float64))
    assert abs(old[0]-new[0])<1e-12
    assert torch.allclose(old[1],torch.cat((new[1][:384],new[1][-1:])),atol=1e-10,rtol=1e-12)
    with tempfile.TemporaryDirectory() as temp:
        os.environ['CARD_CONDITION_EXPERIMENT_DIR']=temp;os.environ['SURFACE_RANK_FOLD']='0'
        c,b,diag=chunked.fit_detail_head(augmented,valid,target,pt,mass,normal_reduction='max_bound')
        audit=json.loads((Path(temp)/'component-gradients-fold0.json').read_text())
        assert c.shape==(385,) and torch.isfinite(c).all() and torch.isfinite(b) and diag['max_gradient']<=1e-5
        assert len(audit['total']['gradient'])==386 and audit['gradient_sum_max_error']<=1e-10
        assert audit['components']['arithmetic_rank']['loss']==0
    counts={p.name:sum(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for node in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS: fold-only worker boundary, zero-added-weight loss/gradient parity, actual385D synthetic fit/component audit')
    print(json.dumps(dict(function_counts=counts,real_training_calls=0,real_photos_used=0,max_project_transitions=4)))
