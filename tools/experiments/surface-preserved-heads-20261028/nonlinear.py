"""Single predeclared eight-unit tanh head; no seed/width search."""
import math
import torch
from card_condition.detail_bag import detail_bag_loss


def nonlinear_logits(x,state):
    return torch.tanh((x.double()-state['center'])@state['hidden_weight']+state['hidden_bias'])@state['output_weight']+state['output_bias']


def fit_nonlinear(features,masks,targets,point_tokens,weights):
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    valid=torch.as_tensor(masks,device='cpu');y=torch.as_tensor(targets,device='cpu');points=torch.as_tensor(point_tokens,device='cpu');mass=torch.as_tensor(weights,device='cpu',dtype=torch.float64)
    if (x.ndim!=3 or valid.shape!=x.shape[:2] or valid.dtype!=torch.bool or not valid.any(1).all()
        or y.shape!=(len(x),) or points.shape!=y.shape or points.dtype!=torch.long or mass.shape!=y.shape
        or not torch.isfinite(x).all() or not torch.isfinite(mass).all() or (mass<=0).any() or set(y.tolist())!={0,1}):
        raise ValueError('Finite explicit binary bags, existing integer points and positive masses required')
    mass=mass/mass.sum()
    for i in range(len(x)):detail_bag_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],None if points[i]<0 else int(points[i]),'max_bound')
    summary=torch.stack([x[i,points[i]] if y[i]==1 and points[i]>=0 else x[i,valid[i]].mean(0) for i in range(len(x))])
    center=(summary*mass[:,None]).sum(0)
    generator=torch.Generator(device='cpu').manual_seed(0)
    state=dict(center=center,hidden_weight=(torch.randn(x.shape[2],8,generator=generator,dtype=torch.float64)/math.sqrt(x.shape[2])).requires_grad_(),hidden_bias=torch.zeros(8,dtype=torch.float64,requires_grad=True),output_weight=torch.zeros(8,dtype=torch.float64,requires_grad=True),output_bias=torch.zeros((),dtype=torch.float64,requires_grad=True))
    params=[state[k] for k in ('hidden_weight','hidden_bias','output_weight','output_bias')]
    assert float(nonlinear_logits(x,state).detach().abs().max())==0
    optimizer=torch.optim.LBFGS(params,max_iter=100,tolerance_grad=1e-7,tolerance_change=1e-12,history_size=20,line_search_fn='strong_wolfe')
    def closure():
        optimizer.zero_grad();z=nonlinear_logits(x,state)
        loss=sum(mass[i]*detail_bag_loss(z[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),'max_bound') for i in range(len(x)))+.5*(state['hidden_weight'].square().sum()+state['output_weight'].square().sum())
        if not torch.isfinite(loss):raise ValueError('Non-finite MLP objective')
        loss.backward();return loss
    initial=float(closure().detach());optimizer.step(closure);objective=float(closure().detach());gradient=max(float(p.grad.abs().max()) for p in params)
    if not math.isfinite(gradient) or gradient>1e-5:raise ValueError(f'MLP did not converge: max_gradient={gradient!r}, objective={objective!r}')
    saved={k:v.detach().clone() for k,v in state.items()};assert all(torch.isfinite(v).all() for v in saved.values())
    return saved,dict(converged=True,train_objective=objective,max_gradient=gradient,initial_objective=initial,initial_logit_max=0.,hidden_units=8,parameter_count=sum(p.numel() for p in params))
