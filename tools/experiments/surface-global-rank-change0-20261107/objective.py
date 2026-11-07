"""Local presence supervision stays distinct from exact human point supervision."""
import math
import json
import os
from pathlib import Path
import torch
from torch.nn import functional as F
from card_condition.point_patch_head import point_bag_loss


def detail_bag_loss(logits, target, valid_mask, point_token=None, normal_reduction='mean_odds'):
    if type(target) is not int or target not in (0, 1):
        raise ValueError('Explicit binary human truth is required')
    if target==0 and point_token is not None:
        if type(point_token) is not int or not 0<=point_token<len(logits) or not valid_mask[point_token]:
            raise ValueError('A known inner-surface confounder point must be a valid photo token')
        # This is a non-edge training role; original surface1 truth is retained separately.
        return F.softplus(logits[point_token])
    if point_token is not None:
        return point_bag_loss(logits, target, valid_mask, point_token, normal_reduction)
    normal_loss = point_bag_loss(logits, 0, valid_mask, normal_reduction=normal_reduction)
    if target == 0:
        return normal_loss
    # Only require a response somewhere in the confirmed bag. This maximum is not a human point.
    return F.softplus(-logits[valid_mask].max())


def save_diagnostics(coef, bias, optimizer, loss, stage):
    state=optimizer.state[coef]
    values=dict(stage=stage,fold=int(os.environ['SURFACE_RANK_FOLD']),
        objective=repr(float(loss)),coefficient_gradient=repr(float(coef.grad.abs().max())) if coef.grad is not None else None,
        bias_gradient=repr(float(bias.grad.abs())) if bias.grad is not None else None,
        coefficient_gradient_finite=bool(torch.isfinite(coef.grad).all()) if coef.grad is not None else None,
        bias_gradient_finite=bool(torch.isfinite(bias.grad).all()) if bias.grad is not None else None,
        n_iter=state.get('n_iter'),func_evals=state.get('func_evals'),
        last_step=repr(state.get('t')),max_iter=1000,max_gradient=1e-5)
    values.update(prev_loss=repr(state.get('prev_loss')),final_loss=repr(float(loss)),
        loss_difference=repr(float(loss)-state['prev_loss']) if state.get('prev_loss') is not None else None,
        absolute_loss_difference=repr(abs(float(loss)-state['prev_loss'])) if state.get('prev_loss') is not None else None,
        tolerance_change=optimizer.param_groups[0]['tolerance_change'],max_eval=optimizer.param_groups[0]['max_eval'])
    if 'd' in state and 't' in state:
        values['last_parameter_step_max']=repr(float((state['d']*state['t']).abs().max()))
        values['directional_derivative']=repr(float(state['d'].dot(optimizer._gather_flat_grad())))
    path=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])/('fit-diagnostics-fold'+str(values['fold'])+'.json')
    path.write_text(json.dumps(values,indent=2,allow_nan=False))


def fit_detail_head(features, masks, targets, point_tokens, weights, penalty=1.0, normal_reduction='mean_odds'):
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
        detail_bag_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
    # Numerical centering of bags is not a point target for weak presence labels.
    summaries=torch.stack([x[i,points[i]] if y[i]==1 and points[i]>=0 else x[i,valid[i]].mean(0)
                           for i in range(len(x))])
    center=(summaries*mass[:,None]).sum(0)
    x=x-center;coef=torch.zeros(x.shape[2],dtype=x.dtype,requires_grad=True)
    bias=torch.zeros((),dtype=x.dtype,requires_grad=True)
    optimizer=torch.optim.LBFGS([coef,bias],max_iter=1000,tolerance_grad=1e-7,
        tolerance_change=0.0,history_size=20,line_search_fn='strong_wolfe')
    def closure():
        optimizer.zero_grad();logits=x@coef+bias
        loss=sum(mass[i]*detail_bag_loss(logits[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
                 for i in range(len(x)))+.5*penalty*coef.square().sum()
        if not torch.isfinite(loss):raise ValueError('Non-finite local detail objective')
        z=logits.masked_fill(~valid, -torch.inf).amax(dim=1)
        loss=loss+F.softplus(z[y==0][None,:]-z[y==1][:,None]).mean()
        if not torch.isfinite(loss):
            save_diagnostics(coef,bias,optimizer,loss,'nonfinite_total_loss')
            raise ValueError('Non-finite total ranking objective')
        loss.backward();return loss
    try:
        optimizer.step(closure);objective=float(closure().detach())
    except Exception:
        save_diagnostics(coef,bias,optimizer,float('nan'),'optimizer_exception')
        raise
    save_diagnostics(coef,bias,optimizer,objective,'post_step')
    gradient=max(float(coef.grad.abs().max()),float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient>1e-5:
        raise ValueError('Detail head did not converge')
    weight=coef.detach().float();intercept=(bias.detach()-center@coef.detach()).float()
    if not torch.isfinite(weight).all() or not torch.isfinite(intercept):
        raise ValueError('Non-finite detail head parameters')
    return weight,intercept,dict(converged=True,train_objective=objective,max_gradient=gradient,
        point_positive_bags=int(((y==1)&(points>=0)).sum()),
        presence_positive_bags=int(((y==1)&(points<0)).sum()))
