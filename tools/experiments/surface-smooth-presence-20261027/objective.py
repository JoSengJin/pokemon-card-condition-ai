"""Experiment-only smooth weak-presence pooling; human point and normal losses stay exact."""
import math
import torch
from torch.nn import functional as F
from card_condition.detail_bag import detail_bag_loss as original_detail_bag_loss


def smooth_presence_loss(logits, target, valid_mask, point_token=None, normal_reduction='mean_odds'):
    baseline = original_detail_bag_loss(logits, target, valid_mask, point_token, normal_reduction)
    if target != 1 or point_token is not None:
        return baseline
    values = logits[valid_mask]
    pooled = .1 * (torch.logsumexp(values / .1, 0) - math.log(len(values)))
    return F.softplus(-pooled)


def fit_smooth_presence(features, masks, targets, point_tokens, weights, penalty=1.0, normal_reduction='mean_odds'):
    if normal_reduction not in ('mean_odds','max_bound'):
        raise ValueError('Unknown normal bag objective')
    if type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:
        raise ValueError('Positive finite regularization is required')
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    valid=torch.as_tensor(masks,device='cpu');y=torch.as_tensor(targets,device='cpu')
    points=torch.as_tensor(point_tokens,device='cpu');mass=torch.as_tensor(weights,device='cpu',dtype=torch.float64)
    if (x.ndim!=3 or not x.shape[2] or valid.shape!=x.shape[:2] or valid.dtype!=torch.bool
            or y.shape!=(len(x),) or y.dtype==torch.bool or points.shape!=y.shape or points.dtype!=torch.long
            or mass.shape!=y.shape or not torch.isfinite(x).all() or not valid.any(1).all()
            or not torch.isfinite(mass).all() or (mass<0).any() or not ((y==0)|(y==1)).all()):
        raise ValueError('Finite labelled patch bags, integer points and valid masses are required')
    keep=mass>0;x,valid,y,points,mass=x[keep],valid[keep],y[keep],points[keep],mass[keep]
    if len(y.unique())!=2 or not torch.isfinite(mass.sum()):
        raise ValueError('Both confirmed human classes are required before fitting')
    mass=mass/mass.sum()
    for i in range(len(x)):
        smooth_presence_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
    # Numerical centering of bags is not a point target for weak presence labels.
    summaries=torch.stack([x[i,points[i]] if y[i]==1 and points[i]>=0 else x[i,valid[i]].mean(0)
                           for i in range(len(x))])
    center=(summaries*mass[:,None]).sum(0)
    x=x-center;coef=torch.zeros(x.shape[2],dtype=x.dtype,requires_grad=True)
    bias=torch.zeros((),dtype=x.dtype,requires_grad=True)
    optimizer=torch.optim.LBFGS([coef,bias],max_iter=100,tolerance_grad=1e-7,
        tolerance_change=1e-12,history_size=20,line_search_fn='strong_wolfe')
    def closure():
        optimizer.zero_grad();logits=x@coef+bias
        loss=sum(mass[i]*smooth_presence_loss(logits[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
                 for i in range(len(x)))+.5*penalty*coef.square().sum()
        if not torch.isfinite(loss):raise ValueError('Non-finite local detail objective')
        loss.backward();return loss
    optimizer.step(closure);objective=float(closure().detach())
    gradient=max(float(coef.grad.abs().max()),float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient>1e-5:
        raise ValueError(f'Detail head did not converge: max_gradient={gradient!r}, objective={objective!r}')
    weight=coef.detach().float();intercept=(bias.detach()-center@coef.detach()).float()
    if not torch.isfinite(weight).all() or not torch.isfinite(intercept):
        raise ValueError('Non-finite detail head parameters')
    return weight,intercept,dict(converged=True,train_objective=objective,max_gradient=gradient,
        point_positive_bags=int(((y==1)&(points>=0)).sum()),
        presence_positive_bags=int(((y==1)&(points<0)).sum()))
