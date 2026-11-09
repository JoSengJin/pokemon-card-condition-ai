"""Synthetic1152D dense oracle, fixed area coding and bounded-memory smoke."""
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
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools/experiments/surface-global-lme-only-20261109'));sys.path.insert(0,str(HERE))
from features import position_features, expand_tokens, score_position
from position_linear import PositionLinear
from card_condition.regions import GLARE_AREAS


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261110)
    rows=[dict(area=area,target=i%2,score=.9) for i,area in enumerate(GLARE_AREAS)]
    x=torch.randn(9,7,384);mask=torch.ones(9,7,dtype=torch.bool);mask[:,3]=False
    original=x.clone();compact=position_features(x,mask,rows);dense=expand_tokens(compact)
    assert torch.equal(compact[:,:,:384],original) and torch.equal(x,original)
    for i in range(9):
        row,column=divmod(i,3);u,v=column-1,row-1
        assert torch.equal(dense[i,mask[i],384:768],x[i,mask[i]]*u)
        assert torch.equal(dense[i,mask[i],768:],x[i,mask[i]]*v)
        assert (dense[i,~mask[i],384:]==0).all()
    altered=[dict(r,target=1-r['target'],score=-100.) for r in rows]
    assert torch.equal(compact,position_features(x,mask,altered))
    for xx,mm,rr in [(x,mask,[dict(area='unknown')]*9),(x,torch.zeros_like(mask),rows),(x*float('nan'),mask,rows),(x,mask.float(),rows),(x[:,:,:383],mask,rows)]:
        try:position_features(xx,mm,rr)
        except ValueError:pass
        else:raise AssertionError('Invalid features/area accepted')
    print('PASS: all9 fixed coordinates, original/mask preservation, labels/scores ignored, invalid inputs rejected')
    max_forward=max_backward=0.
    for n in (1,8,9,19):
        xx=torch.randn(n,7,384);valid=torch.ones(n,7,dtype=torch.bool);valid[:,2]=False
        cc=position_features(xx,valid,[dict(area=GLARE_AREAS[i%9]) for i in range(n)])
        center=torch.randn(1152,dtype=torch.float64);theta=(torch.randn(1153,dtype=torch.float64)*.01).requires_grad_()
        reference=(expand_tokens(cc).double()-center)@theta[:-1]+theta[-1]
        actual=PositionLinear.apply(theta,cc,center);upstream=torch.randn_like(reference)
        ga=torch.autograd.grad(reference,theta,upstream)[0];gb=torch.autograd.grad(actual,theta,upstream)[0]
        max_forward=max(max_forward,float((reference-actual).detach().abs().max()));max_backward=max(max_backward,float((ga-gb).abs().max()))
        assert torch.allclose(reference,actual,atol=1e-12,rtol=1e-12)
        assert torch.allclose(ga,gb,atol=1e-10,rtol=1e-12)
    reference=load('dense_alpha0',ROOT/'tools/experiments/surface-global-lme-only-20261109/objective.py')
    candidate=load('position_alpha0',HERE/'objective.py')
    n=10;xx=torch.randn(n,5,384);valid=torch.ones(n,5,dtype=torch.bool)
    cc=position_features(xx,valid,[dict(area=GLARE_AREAS[i%9]) for i in range(n)])
    theta=torch.randn(1153,dtype=torch.float64)*.01;center=torch.randn(1152,dtype=torch.float64)
    target=torch.tensor([0,1]*5);points=torch.full((n,),-1);mass=torch.full((n,),1/n,dtype=torch.float64)
    a=reference.loss_and_grad(theta,expand_tokens(cc).double()-center,valid,target,points,mass,1.,'max_bound')
    b=candidate.loss_and_grad(theta,cc,valid,target,points,mass,1.,'max_bound',center)
    assert abs(a[0]-b[0])<1e-12 and torch.allclose(a[1],b[1],atol=1e-10,rtol=1e-12)
    for key in a[3][1]:
        ga=torch.autograd.grad(a[3][1][key],a[3][0],retain_graph=True)[0]
        gb=torch.autograd.grad(b[3][1][key],b[3][0],retain_graph=True)[0]
        assert abs(float(a[3][1][key].detach()-b[3][1][key].detach()))<1e-12
        assert torch.allclose(ga,gb,atol=1e-10,rtol=1e-12),key
    # With zero interaction weights the original384D model is recovered.
    base_theta=torch.randn(385,dtype=torch.float64)*.01
    padded=torch.cat((base_theta[:384],torch.zeros(768,dtype=torch.float64),base_theta[-1:]))
    old=reference.loss_and_grad(base_theta,xx.double(),valid,target,points,mass,1.,'max_bound')
    new=candidate.loss_and_grad(padded,cc,valid,target,points,mass,1.,'max_bound',torch.zeros(1152,dtype=torch.float64))
    assert abs(old[0]-new[0])<1e-12 and torch.allclose(old[1],torch.cat((new[1][:384],new[1][-1:])),atol=1e-10,rtol=1e-12)
    coef=torch.randn(1152)*.01;bias=torch.tensor(.03)
    expected=(expand_tokens(cc)@coef+bias).masked_fill(~valid,-torch.inf).amax(1).sigmoid()
    scored=torch.tensor(score_position(cc,valid,coef,bias))
    assert torch.allclose(scored,expected,atol=2e-6,rtol=0)
    with tempfile.TemporaryDirectory() as temp:
        fits=[];xx=torch.zeros(18,3,384);target=torch.tensor([0,1]*9);xx[:,:,0]=torch.where(target==0,-1.,1.)[:,None]
        valid=torch.ones(18,3,dtype=torch.bool);points=torch.full((18,),-1);mass=torch.ones(18)
        cc=position_features(xx,valid,[dict(area=a) for a in GLARE_AREAS for _ in (0,1)])
        for name,module,features in [('dense',reference,expand_tokens(cc)),('factored',candidate,cc)]:
            output=Path(temp)/name;output.mkdir();os.environ['CARD_CONDITION_EXPERIMENT_DIR']=str(output);os.environ['SURFACE_RANK_FOLD']='0'
            fits.append(module.fit_detail_head(features,valid,target,points,mass,normal_reduction='max_bound'))
            audit=json.loads((output/'component-gradients-fold0.json').read_text())
            assert len(audit['total']['gradient'])==1153 and audit['gradient_sum_max_error']<1e-10
            assert audit['components']['arithmetic_rank']['loss']==0 and audit['total']['linf_norm']<=1e-5
        assert torch.allclose(fits[0][0],fits[1][0],atol=1e-6,rtol=1e-6) and torch.allclose(fits[0][1],fits[1][1],atol=1e-6,rtol=1e-6)
    # Full1024-token bags cross an8-bag boundary; training projection holds384D chunks only.
    xx=torch.randn(9,1024,384);valid=torch.ones(9,1024,dtype=torch.bool);cc=position_features(xx,valid,[dict(area=a) for a in GLARE_AREAS])
    theta=torch.zeros(1153,dtype=torch.float64,requires_grad=True);result=PositionLinear.apply(theta,cc,torch.zeros(1152,dtype=torch.float64))
    result.sum().backward()
    assert PositionLinear.max_chunk_rows==8 and PositionLinear.max_base_elements==8*1024*384
    assert cc.shape==(9,1024,386) and theta.grad.shape==(1153,)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS: dense/factored projection, full/component loss-gradient, zero-interaction baseline, float32 scoring, synthetic1152D fit and1024-token memory smoke')
    print(json.dumps(dict(function_counts=counts,max_forward_error=max_forward,max_backward_error=max_backward,projection_max_rows=PositionLinear.max_chunk_rows,projection_max_base_elements=PositionLinear.max_base_elements,base_chunk_float64_bytes=PositionLinear.max_base_elements*8,full_expansion_stored=False,real_photos_used=0,real_training_calls=0)))
