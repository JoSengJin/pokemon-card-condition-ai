"""Experiment-only normal physical-group aggregation; no production model wiring."""
import math
import torch
from card_condition.detail_bag import detail_bag_loss


def fit_normal_group_head(features, masks, targets, point_tokens, weights, groups, penalty=1.0, normal_reduction='max_bound'):
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
    if len(groups)!=len(x) or any(type(g) is not str or not g for g in groups) or (mass<=0).any():
        raise ValueError('Positive mass and explicit physical groups are required')
    normal_groups=sorted({groups[i] for i in range(len(x)) if y[i]==0})
    grouped=[torch.tensor([i for i,g in enumerate(groups) if g==name and y[i]==0]) for name in normal_groups]
    if not normal_groups or not torch.allclose(mass[y==0].sum(),mass[y==1].sum()):
        raise ValueError('Frozen equal class masses are required')
    keep=mass>0;x,valid,y,points,mass=x[keep],valid[keep],y[keep],points[keep],mass[keep]
    if len(y.unique())!=2 or not torch.isfinite(mass.sum()):
        raise ValueError('Both confirmed human classes are required before fitting')
    mass=mass/mass.sum()
    for i in range(len(x)):
        detail_bag_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
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
        losses=torch.stack([detail_bag_loss(logits[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
                            for i in range(len(x))])
        group_losses=torch.stack([(losses[idx]*mass[idx]).sum()/mass[idx].sum() for idx in grouped])
        group_mass=torch.stack([mass[idx].sum() for idx in grouped])
        normal=.1*torch.logsumexp(group_losses/.1+(group_mass/group_mass.sum()).log(),0)
        loss=(mass[y==1]*losses[y==1]).sum()+mass[y==0].sum()*normal+.5*penalty*coef.square().sum()
        if not torch.isfinite(loss):raise ValueError('Non-finite local detail objective')
        loss.backward();return loss
    optimizer.step(closure);objective=float(closure().detach())
    gradient=max(float(coef.grad.abs().max()),float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient>1e-5:
        raise ValueError('Detail head did not converge')
    weight=coef.detach().float();intercept=(bias.detach()-center@coef.detach()).float()
    if not torch.isfinite(weight).all() or not torch.isfinite(intercept):
        raise ValueError('Non-finite detail head parameters')
    return weight,intercept,dict(converged=True,train_objective=objective,max_gradient=gradient,
        point_positive_bags=int(((y==1)&(points>=0)).sum()),
        presence_positive_bags=int(((y==1)&(points<0)).sum()))
