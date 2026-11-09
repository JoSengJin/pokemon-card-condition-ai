"""Synthetic extraction parity,768D dense oracle and bounded-memory smoke."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock,patch
import torch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools/experiments/surface-global-lme-only-20261109'));sys.path.insert(0,str(HERE))
import features
from features import expand_tokens,score_cls
from cls_linear import CLSLinear


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261110)
    original=load('original_extractor',ROOT/'tools/experiments/surface-negfilter-cv-20261104/worker.py')
    rows=[dict(id=str(i),image='fixture',box=[0.,0.,1.,1.],target=i%2) for i in range(3)]
    patches=torch.randn(3,1024,384);contexts=torch.randn(3,384)
    outputs=[dict(x_norm_patchtokens=patches[i:i+1],x_norm_clstoken=contexts[i:i+1]) for i in range(3)]
    views=[torch.zeros(3,448,448)]*3;physical=torch.ones(448,448,dtype=torch.bool)
    body=MagicMock();body.forward_features.side_effect=outputs
    with patch.object(features,'view_tensors',return_value=views) as v,patch.object(features,'physical_pixel_mask',return_value=physical) as pm:
        x,m,c=features.backbone_features(body,rows,'cpu')
        assert v.call_args.args==('fixture',[r['box'] for r in rows],448)
        assert all(call.kwargs==dict(halo=0,image_size=448) for call in pm.call_args_list)
    assert body.forward_features.call_count==3 and torch.equal(x,patches) and torch.equal(c,contexts)
    body.forward_features.side_effect=outputs
    with patch.object(original,'view_tensors',return_value=views),patch.object(original,'physical_pixel_mask',return_value=physical):
        old_x,old_m=original.backbone_features(body,rows,'cpu')
    assert torch.equal(old_x,x) and torch.equal(old_m,m)
    body.forward_features.side_effect=outputs
    with patch.object(features,'view_tensors',return_value=views),patch.object(features,'physical_pixel_mask',return_value=physical):
        altered=features.backbone_features(body,[dict(r,target=1-r['target'],score=-100.,area='unknown') for r in rows],'cpu')
    assert all(torch.equal(a,b) for a,b in zip((x,m,c),altered))
    print('PASS: same crop/mask/raw patches as original; one forward per crop; same-forward CLS; labels/scores/area unused')
    max_forward=max_backward=0.
    for n in (1,8,9,19):
        x=torch.randn(n,7,384);c=torch.randn(n,384);valid=torch.ones(n,7,dtype=torch.bool);valid[:,2]=False
        dense=expand_tokens(x,c,valid)
        assert torch.equal(dense[...,:384],x)
        assert (dense[...,384:][~valid]==0).all()
        assert torch.equal(dense[...,384:][valid],(x*c[:,None,:])[valid])
        center=torch.randn(768,dtype=torch.float64);theta=(torch.randn(769,dtype=torch.float64)*.01).requires_grad_()
        reference=(dense.double()-center)@theta[:-1]+theta[-1]
        actual=CLSLinear.apply(theta,x,c,valid,center);upstream=torch.randn_like(reference)
        ga=torch.autograd.grad(reference,theta,upstream)[0];gb=torch.autograd.grad(actual,theta,upstream)[0]
        max_forward=max(max_forward,float((reference-actual).detach().abs().max()));max_backward=max(max_backward,float((ga-gb).abs().max()))
        assert torch.allclose(reference,actual,atol=1e-12,rtol=1e-12)
        assert torch.allclose(ga,gb,atol=1e-10,rtol=1e-12)
    for xx,cc,mm in [(x[:,:,:383],c,valid),(x,c[:,:383],valid),(x,c*float('nan'),valid),(x, c,valid.float()),(x.double(),c,valid)]:
        try:expand_tokens(xx,cc,mm)
        except ValueError:pass
        else:raise AssertionError('Invalid representation input accepted')
    reference=load('dense_alpha0',ROOT/'tools/experiments/surface-global-lme-only-20261109/objective.py')
    candidate=load('cls_alpha0',HERE/'objective.py')
    n=10;x=torch.randn(n,5,384);c=torch.randn(n,384);valid=torch.ones(n,5,dtype=torch.bool);valid[:,2]=False
    theta=torch.randn(769,dtype=torch.float64)*.01;center=torch.randn(768,dtype=torch.float64)
    target=torch.tensor([0,1]*5);points=torch.full((n,),-1);points[0]=0;points[1]=1
    mass=torch.full((n,),1/n,dtype=torch.float64)
    a=reference.loss_and_grad(theta,expand_tokens(x,c,valid).double()-center,valid,target,points,mass,1.,'max_bound')
    b=candidate.loss_and_grad(theta,x,valid,target,points,mass,1.,'max_bound',center,c)
    assert abs(a[0]-b[0])<1e-12 and torch.allclose(a[1],b[1],atol=1e-10,rtol=1e-12)
    for key in a[3][1]:
        ga=torch.autograd.grad(a[3][1][key],a[3][0],retain_graph=True)[0]
        gb=torch.autograd.grad(b[3][1][key],b[3][0],retain_graph=True)[0]
        assert abs(float(a[3][1][key].detach()-b[3][1][key].detach()))<1e-12
        assert torch.allclose(ga,gb,atol=1e-10,rtol=1e-12),key
    base_theta=torch.randn(385,dtype=torch.float64)*.01
    padded=torch.cat((base_theta[:384],torch.zeros(384,dtype=torch.float64),base_theta[-1:]))
    old=reference.loss_and_grad(base_theta,x.double(),valid,target,points,mass,1.,'max_bound')
    new=candidate.loss_and_grad(padded,x,valid,target,points,mass,1.,'max_bound',torch.zeros(768,dtype=torch.float64),c)
    assert abs(old[0]-new[0])<1e-12 and torch.allclose(old[1],torch.cat((new[1][:384],new[1][-1:])),atol=1e-10,rtol=1e-12)
    coef=torch.randn(768)*.01;bias=torch.tensor(.03)
    expected=(expand_tokens(x,c,valid)@coef+bias).masked_fill(~valid,-torch.inf).amax(1).sigmoid()
    scored=torch.tensor(score_cls(x,valid,c,coef,bias))
    assert torch.allclose(scored,expected,atol=2e-6,rtol=0)
    with tempfile.TemporaryDirectory() as temp:
        fits=[];x=torch.zeros(18,3,384);target=torch.tensor([0,1]*9);x[:,:,0]=torch.where(target==0,-1.,1.)[:,None]
        c=torch.ones(18,384);valid=torch.ones(18,3,dtype=torch.bool);points=torch.full((18,),-1);mass=torch.ones(18)
        for name,module,data,kwargs in [('dense',reference,expand_tokens(x,c,valid),{}),('chunk',candidate,x,dict(cls=c))]:
            output=Path(temp)/name;output.mkdir();os.environ['CARD_CONDITION_EXPERIMENT_DIR']=str(output);os.environ['SURFACE_RANK_FOLD']='0'
            fits.append(module.fit_detail_head(data,valid,target,points,mass,normal_reduction='max_bound',**kwargs))
            audit=json.loads((output/'component-gradients-fold0.json').read_text())
            assert len(audit['total']['gradient'])==769 and audit['gradient_sum_max_error']<1e-10
            assert audit['components']['arithmetic_rank']['loss']==0 and audit['total']['linf_norm']<=1e-5
        assert torch.allclose(fits[0][0],fits[1][0],atol=1e-6,rtol=1e-6) and torch.allclose(fits[0][1],fits[1][1],atol=1e-6,rtol=1e-6)
    x=torch.randn(9,1024,384);c=torch.randn(9,384);valid=torch.ones(9,1024,dtype=torch.bool)
    theta=torch.zeros(769,dtype=torch.float64,requires_grad=True)
    result=CLSLinear.apply(theta,x,c,valid,torch.zeros(768,dtype=torch.float64));result.sum().backward()
    assert CLSLinear.max_chunk_rows==8 and CLSLinear.max_base_elements==8*1024*384 and theta.grad.shape==(769,)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS: raw preservation/invalid0/input guards; dense/chunk output and full/component gradients; zero-interaction baseline; float32 scoring; synthetic768D fit;1024-token chunk memory')
    print(json.dumps(dict(function_counts=counts,max_forward_error=max_forward,max_backward_error=max_backward,projection_max_rows=CLSLinear.max_chunk_rows,projection_max_base_elements=CLSLinear.max_base_elements,base_chunk_float64_bytes=CLSLinear.max_base_elements*8,product_chunk_float64_bytes=CLSLinear.max_base_elements*8,full_expansion_stored=False,real_photos_used=0,real_training_calls=0)))
