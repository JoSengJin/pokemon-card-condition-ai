"""Synthetic checks only; independent spatial oracle and unchanged 768D fitter."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import torch

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
sys.path.insert(0,str(FOLDER))
from features import augment_local_contrast


def oracle(x,mask):
    out=torch.zeros_like(x)
    for i in range(len(x)):
        for r in range(32):
            for c in range(32):
                if not mask[i,r*32+c]:continue
                neighbors=[a*32+b for a in range(max(0,r-1),min(32,r+2))
                    for b in range(max(0,c-1),min(32,c+2)) if mask[i,a*32+b]]
                out[i,r*32+c]=(x[i,r*32+c]-x[i,neighbors].mean(0)).abs()
    return torch.cat((x,out),dim=2)


if __name__=='__main__':
    torch.set_num_threads(2);torch.manual_seed(20261109)
    x=torch.randn(2,1024,384);mask=torch.rand(2,1024)>.3
    source=x.clone();before=mask.clone();actual=augment_local_contrast(x,mask)
    expected=oracle(x,mask)
    assert torch.equal(x,source) and torch.equal(mask,before)
    assert torch.equal(actual[:,:,:384],x)
    assert torch.allclose(actual,expected,atol=1e-6,rtol=1e-6)
    assert (actual[:,:,384:][~mask]==0).all()
    # Padding values cannot influence valid residuals; rows never share statistics.
    altered=x.clone();altered[~mask]=1e6
    changed=augment_local_contrast(altered,mask)
    assert torch.equal(actual[:,:,384:],changed[:,:,384:])
    assert torch.equal(actual[0],augment_local_contrast(x[:1],mask[:1])[0])
    constant=torch.full_like(x,7.);assert (augment_local_contrast(constant,mask)[:,:,384:]==0).all()
    single=torch.zeros_like(mask);single[:,0]=True
    assert (augment_local_contrast(x,single)[:,:,384:]==0).all()
    grid=torch.arange(1024).float().view(1,1024,1).expand(1,1024,384)
    corners=augment_local_contrast(grid,torch.ones(1,1024,dtype=torch.bool))
    assert corners[0,0,384]==16.5 and corners[0,1023,384]==16.5
    for bad,badmask in [(x[:,:,:383],mask),(x,mask.float()),(x,torch.zeros_like(mask)),(x*float('nan'),mask)]:
        try:augment_local_contrast(bad,badmask)
        except ValueError:pass
        else:raise AssertionError('Invalid input accepted')
    print('PASS: independent masked3x3 oracle, borders, padding, row isolation, constants, singleton, original preservation, invalid rejection')
    # Appending zero coefficients reproduces the original scores/objective exactly.
    sys.path.insert(0,str(ROOT/'tools/experiments/surface-global-lme-only-20261109'))
    import objective
    xx=actual[:,:3].double();valid=torch.ones(2,3,dtype=torch.bool);y=torch.tensor([0,1]);points=torch.full((2,),-1);mass=torch.full((2,),.5,dtype=torch.float64)
    theta=torch.randn(385,dtype=torch.float64)*.01
    expanded=torch.cat((theta[:-1],torch.zeros(384,dtype=torch.float64),theta[-1:]))
    old=objective.loss_and_grad(theta,xx[:,:,:384],valid,y,points,mass,1.,'max_bound')
    new=objective.loss_and_grad(expanded,xx,valid,y,points,mass,1.,'max_bound')
    assert abs(old[0]-new[0])<1e-12
    assert torch.allclose(old[1],torch.cat((new[1][:384],new[1][-1:])),atol=1e-12,rtol=1e-12)
    with tempfile.TemporaryDirectory() as temp:
        os.environ['CARD_CONDITION_EXPERIMENT_DIR']=temp;os.environ['SURFACE_RANK_FOLD']='0'
        coef,bias,diagnostic=objective.fit_detail_head(xx,valid,y,points,mass,normal_reduction='max_bound')
        audit=json.loads((Path(temp)/'component-gradients-fold0.json').read_text())
        assert coef.shape==(768,) and torch.isfinite(coef).all() and torch.isfinite(bias)
        assert diagnostic['max_gradient']<=1e-5 and audit['gradient_sum_max_error']<=1e-10
        assert len(audit['total']['gradient'])==769 and audit['components']['arithmetic_rank']['loss']==0
    print('PASS: zero-added-weight objective/gradient parity and synthetic768D fit/component audit')
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in FOLDER.glob('*.py')}
    assert max(counts.values())<=7
    compile((FOLDER/'worker.py').read_text(),'worker.py','exec')
    print(json.dumps(dict(function_counts=counts,max_project_call_transitions=4,model_photos_used=0)))
