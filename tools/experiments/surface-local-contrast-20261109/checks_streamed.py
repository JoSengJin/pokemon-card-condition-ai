"""Synthetic dense-vs-chunked oracle, including custom backward and actual fitter."""
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
sys.path.insert(0,str(ROOT/'tools/experiments/surface-global-lme-only-20261109'))
sys.path.insert(0,str(HERE))
from streamed_linear import StreamedLinear


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261109)
    old=load('dense_alpha0',ROOT/'tools/experiments/surface-global-lme-only-20261109/objective.py')
    new=load('streamed_alpha0',HERE/'objective.py')
    maximum=0.
    for n in (1,8,9,19):
        x=torch.randn(n,7,768);center=torch.randn(768,dtype=torch.float64);theta=(torch.randn(769,dtype=torch.float64)*.1).requires_grad_()
        reference=(x.double()-center)@theta[:-1]+theta[-1]
        candidate=StreamedLinear.apply(theta,x,center)
        upstream=torch.randn_like(reference)
        a=torch.autograd.grad(reference,theta,upstream)[0]
        b=torch.autograd.grad(candidate,theta,upstream)[0]
        maximum=max(maximum,float((a-b).abs().max()))
        assert torch.allclose(reference,candidate,atol=1e-12,rtol=1e-12)
        assert torch.allclose(a,b,atol=1e-10,rtol=1e-12)
    print('PASS: custom forward/backward vs dense projection at 1/8/9/19 rows; maximum gradient error',maximum)
    x=torch.randn(12,5,768);valid=torch.rand(12,5)>.3;valid[:,0]=True
    y=torch.tensor([0,1]*6);points=torch.full((12,),-1);mass=torch.full((12,),1/12,dtype=torch.float64)
    center=torch.randn(768,dtype=torch.float64);theta=torch.randn(769,dtype=torch.float64)*.01
    a=old.loss_and_grad(theta,x.double()-center,valid,y,points,mass,1.,'max_bound')
    b=new.loss_and_grad(theta,x,valid,y,points,mass,1.,'max_bound',center)
    assert abs(a[0]-b[0])<1e-12 and torch.allclose(a[1],b[1],atol=1e-10,rtol=1e-12)
    for key in a[3][1]:
        ga=torch.autograd.grad(a[3][1][key],a[3][0],retain_graph=True)[0]
        gb=torch.autograd.grad(b[3][1][key],b[3][0],retain_graph=True)[0]
        assert abs(float(a[3][1][key].detach()-b[3][1][key].detach()))<1e-12
        assert torch.allclose(ga,gb,atol=1e-10,rtol=1e-12),key
    with tempfile.TemporaryDirectory() as temp:
        output=Path(temp);fits=[]
        # 10 rows crosses the chunk boundary. Same synthetic data in both fitters.
        xx=torch.zeros(10,3,768);xx[:,:,0]=torch.tensor([-1.,1.]*5)[:,None]
        mask=torch.ones(10,3,dtype=torch.bool);target=torch.tensor([0,1]*5);pt=torch.full((10,),-1);weight=torch.ones(10)
        for name,module in [('dense',old),('streamed',new)]:
            folder=output/name;folder.mkdir();os.environ['CARD_CONDITION_EXPERIMENT_DIR']=str(folder);os.environ['SURFACE_RANK_FOLD']='0'
            fits.append(module.fit_detail_head(xx,mask,target,pt,weight,normal_reduction='max_bound'))
            record=json.loads((folder/'component-gradients-fold0.json').read_text())
            assert record['gradient_sum_max_error']<1e-10 and len(record['total']['gradient'])==769
            assert record['components']['arithmetic_rank']['loss']==0
            assert record['total']['linf_norm']<=1e-5
        assert torch.allclose(fits[0][0],fits[1][0],atol=1e-6,rtol=1e-6)
        assert torch.allclose(fits[0][1],fits[1][1],atol=1e-6,rtol=1e-6)
    counts={p.name:sum(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for node in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS: dense/streamed full objective and all5 component gradients, actual768D fit, final gradient/component audit')
    print(json.dumps(dict(function_counts=counts,real_training_calls=0,real_photos_used=0)))
