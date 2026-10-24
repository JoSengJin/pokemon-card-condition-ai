"""Opt-in research head: human point positives and normal photographic patch bags."""
import math
import torch
from torch.nn import functional as F


def point_bag_loss(logits,target,valid_mask,point_token=-1,normal_reduction='mean_odds'):
    if normal_reduction not in ('mean_odds','max_bound'):
        raise ValueError('Unknown normal bag objective')
    if (logits.ndim!=1 or not torch.isfinite(logits).all() or type(target) is not int
            or target not in (0,1) or valid_mask.dtype!=torch.bool
            or valid_mask.shape!=logits.shape or not valid_mask.any()):
        raise ValueError('Expected finite patch logits, binary truth and nonempty photo mask')
    if target==1:
        if type(point_token) is not int or not 0<=point_token<len(logits) or not valid_mask[point_token]:
            raise ValueError('Positive bag requires a valid human point token')
        return F.softplus(-logits[point_token])
    values=logits[valid_mask]
    if normal_reduction=='max_bound':
        # Fixed smooth upper bound matches max-token warnings without diluting rare alarms.
        return F.softplus(.1*torch.logsumexp(values/.1,0))
    # Average odds penalizes rare large false alarms more than average patch BCE.
    return F.softplus(torch.logsumexp(values,0)-math.log(len(values)))


def fit_point_bag_head(features,masks,targets,point_tokens,weights,penalty=1.0,normal_reduction='mean_odds'):
    if normal_reduction not in ('mean_odds','max_bound'):
        raise ValueError('Unknown normal bag objective')
    if type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:
        raise ValueError('Expected positive finite regularization')
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    valid=torch.as_tensor(masks,device='cpu')
    y=torch.as_tensor(targets,device='cpu')
    points=torch.as_tensor(point_tokens,device='cpu')
    mass=torch.as_tensor(weights,device='cpu',dtype=torch.float64)
    if (x.ndim!=3 or not x.shape[2] or valid.shape!=x.shape[:2] or valid.dtype!=torch.bool
            or y.shape!=(len(x),) or points.shape!=y.shape or mass.shape!=y.shape
            or not torch.isfinite(x).all() or not torch.isfinite(mass).all()
            or (mass<0).any() or not ((y==0)|(y==1)).all()
            or points.dtype!=torch.long or not valid.any(1).all()):
        raise ValueError('Expected finite patch bags, masks, binary truth, integer points and masses')
    keep=mass>0;x,valid,y,points,mass=x[keep],valid[keep],y[keep],points[keep],mass[keep]
    if len(y.unique())!=2 or not torch.isfinite(mass.sum()):
        raise ValueError('Both human classes require positive finite training mass')
    mass=mass/mass.sum()
    for i in range(len(x)):
        point_bag_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],int(points[i]),normal_reduction)
    summaries=torch.stack([x[i,points[i]] if y[i] else x[i,valid[i]].mean(0) for i in range(len(x))])
    center=(summaries*mass[:,None]).sum(0);x=x-center
    coef=torch.zeros(x.shape[2],dtype=x.dtype,requires_grad=True)
    bias=torch.zeros((),dtype=x.dtype,requires_grad=True)
    optimizer=torch.optim.LBFGS([coef,bias],max_iter=100,tolerance_grad=1e-7,
        tolerance_change=1e-12,history_size=20,line_search_fn='strong_wolfe')
    evaluations=0
    def closure():
        nonlocal evaluations
        optimizer.zero_grad();logits=x@coef+bias
        loss=sum(mass[i]*point_bag_loss(logits[i],int(y[i]),valid[i],int(points[i]),normal_reduction)
                 for i in range(len(x)))+.5*penalty*coef.square().sum()
        if not torch.isfinite(loss):raise ValueError('Non-finite point-bag objective')
        loss.backward();evaluations+=1
        return loss
    optimizer.step(closure);objective=float(closure().detach())
    gradient=max(float(coef.grad.abs().max()),float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient>1e-5:
        raise ValueError('Point-bag head did not converge on training objective')
    result=coef.detach().float();intercept=(bias.detach()-center@coef.detach()).float()
    if not torch.isfinite(result).all() or not torch.isfinite(intercept):
        raise ValueError('Non-finite point-bag head')
    return result,intercept,dict(converged=True,train_objective=objective,
        max_gradient=gradient,objective_evaluations=evaluations,fit_bags=len(x))
