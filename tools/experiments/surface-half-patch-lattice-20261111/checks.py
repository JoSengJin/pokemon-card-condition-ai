"""Synthetic checks: shifted-lattice extraction, chunked 384D projection vs dense oracle, alpha0 objective equivalence, memory smoke."""
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
from features import score_tokens,shifted
from tok_linear import TokLinear


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261111)
    original=load('original_extractor',ROOT/'tools/experiments/surface-negfilter-cv-20261104/worker.py')
    rows=[dict(id=str(i),image='fixture',box=[0.,0.,1.,1.],target=i%2) for i in range(2)]
    views=[torch.randn(3,448,448) for _ in rows];physical=torch.zeros(448,448,dtype=torch.bool);physical[20:400,30:420]=True
    outputs=[dict(x_norm_patchtokens=torch.randn(1,1024,384)) for _ in range(4)]
    seen=[]
    body=MagicMock();body.forward_features.side_effect=lambda t:(seen.append(t.clone()),outputs[len(seen)-1])[1]
    with patch.object(features,'view_tensors',return_value=views),patch.object(features,'physical_pixel_mask',return_value=physical):
        x,m=features.backbone_features(body,rows,'cpu')
    assert body.forward_features.call_count==4 and x.shape==(2,2048,384) and m.shape==(2,2048)
    for i in range(2):
        assert torch.equal(seen[2*i][0],views[i]) and torch.equal(seen[2*i+1][0],shifted(views[i],7))
        assert torch.equal(seen[2*i+1][0][:,:441,:441],views[i][:,7:,7:]) and (seen[2*i+1][0][:,441:,:]==0).all() and (seen[2*i+1][0][:,:,441:]==0).all()
        assert torch.equal(x[i,:1024],outputs[2*i]['x_norm_patchtokens'][0]) and torch.equal(x[i,1024:],outputs[2*i+1]['x_norm_patchtokens'][0])
        grid=shifted(physical,7).reshape(32,14,32,14).any(3).any(1);grid[31,:]=False;grid[:,31]=False
        assert torch.equal(m[i,1024:],grid.flatten()) and not m[i,1024:].view(32,32)[31].any() and not m[i,1024:].view(32,32)[:,31].any()
    body.forward_features.side_effect=[dict(x_norm_patchtokens=o['x_norm_patchtokens']) for o in outputs[:2]]
    with patch.object(original,'view_tensors',return_value=views[:1]),patch.object(original,'physical_pixel_mask',return_value=physical):
        old_x,old_m=original.backbone_features(body,rows[:1],'cpu')
    assert torch.equal(old_x[0],x[0,:1024]) and torch.equal(old_m[0],m[0,:1024])
    seen.clear();body.forward_features.side_effect=lambda t:(seen.append(t),outputs[len(seen)-1])[1]
    with patch.object(features,'view_tensors',return_value=views),patch.object(features,'physical_pixel_mask',return_value=physical):
        altered=features.backbone_features(body,[dict(r,target=1-r['target'],score=-9.,area='u') for r in rows],'cpu')
    assert torch.equal(altered[0],x) and torch.equal(altered[1],m)
    print('PASS: first lattice identical to original extractor; second lattice = 7px up-left shift with zero band; last row/col invalid; 2048-token order; labels/scores unused')
    max_forward=max_backward=0.
    for n in (1,8,9,19):
        xx=torch.randn(n,7,384);valid=torch.ones(n,7,dtype=torch.bool);valid[:,2]=False
        center=torch.randn(384,dtype=torch.float64);theta=(torch.randn(385,dtype=torch.float64)*.01).requires_grad_()
        dense=(xx.double()-center)@theta[:-1]+theta[-1];actual=TokLinear.apply(theta,xx,valid,center);up=torch.randn_like(dense)
        ga=torch.autograd.grad(dense,theta,up)[0];gb=torch.autograd.grad(actual,theta,up)[0]
        max_forward=max(max_forward,float((dense-actual).detach().abs().max()));max_backward=max(max_backward,float((ga-gb).abs().max()))
        assert torch.allclose(dense,actual,atol=1e-12,rtol=1e-12) and torch.allclose(ga,gb,atol=1e-10,rtol=1e-12)
    reference=load('dense_alpha0',ROOT/'tools/experiments/surface-global-lme-only-20261109/objective.py')
    candidate=load('lattice_alpha0',HERE/'objective.py')
    n=10;xx=torch.randn(n,5,384);valid=torch.ones(n,5,dtype=torch.bool);valid[:,2]=False
    theta=torch.randn(385,dtype=torch.float64)*.01;center=torch.randn(384,dtype=torch.float64)
    target=torch.tensor([0,1]*5);points=torch.full((n,),-1);mass=torch.full((n,),1/n,dtype=torch.float64)
    a=reference.loss_and_grad(theta,xx.double()-center,valid,target,points,mass,1.,'max_bound')
    b=candidate.loss_and_grad(theta,xx,valid,target,points,mass,1.,'max_bound',center)
    assert abs(a[0]-b[0])<1e-12 and torch.allclose(a[1],b[1],atol=1e-10,rtol=1e-12) and torch.equal(a[2],b[2])
    for key in a[3][1]:
        assert abs(float(a[3][1][key].detach()-b[3][1][key].detach()))<1e-12
        assert torch.allclose(torch.autograd.grad(a[3][1][key],a[3][0],retain_graph=True)[0],torch.autograd.grad(b[3][1][key],b[3][0],retain_graph=True)[0],atol=1e-10,rtol=1e-12),key
    coef=torch.randn(384)*.01;bias=torch.tensor(.03)
    assert torch.allclose(torch.tensor(score_tokens(xx,valid,coef,bias)),(xx@coef+bias).masked_fill(~valid,-torch.inf).amax(1).sigmoid(),atol=2e-6,rtol=0)
    with tempfile.TemporaryDirectory() as temp:
        fits=[];xx=torch.zeros(18,3,384);target=torch.tensor([0,1]*9);xx[:,:,0]=torch.where(target==0,-1.,1.)[:,None]
        valid=torch.ones(18,3,dtype=torch.bool);points=torch.full((18,),-1);mass=torch.ones(18)
        for name,module in [('dense',reference),('chunk',candidate)]:
            output=Path(temp)/name;output.mkdir();os.environ['CARD_CONDITION_EXPERIMENT_DIR']=str(output);os.environ['SURFACE_RANK_FOLD']='0'
            fits.append(module.fit_detail_head(xx,valid,target,points,mass,normal_reduction='max_bound'))
            audit=json.loads((output/'component-gradients-fold0.json').read_text())
            assert len(audit['total']['gradient'])==385 and audit['gradient_sum_max_error']<1e-10 and audit['total']['linf_norm']<=1e-5
        assert torch.allclose(fits[0][0],fits[1][0],atol=1e-6,rtol=1e-6) and torch.allclose(fits[0][1],fits[1][1],atol=1e-6,rtol=1e-6)
    xx=torch.randn(9,2048,384);valid=torch.ones(9,2048,dtype=torch.bool);theta=torch.zeros(385,dtype=torch.float64,requires_grad=True)
    TokLinear.apply(theta,xx,valid,torch.zeros(384,dtype=torch.float64)).sum().backward()
    assert TokLinear.max_chunk_rows==8 and TokLinear.max_base_elements==8*2048*384 and theta.grad.shape==(385,)
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS: chunked 384D projection == dense oracle (fwd/bwd); objective/components/fit == alpha0 reference; float32 scoring; 2048-token chunk memory')
    print(json.dumps(dict(function_counts=counts,max_forward_error=max_forward,max_backward_error=max_backward,projection_max_rows=TokLinear.max_chunk_rows,real_photos_used=0,real_training_calls=0)))
