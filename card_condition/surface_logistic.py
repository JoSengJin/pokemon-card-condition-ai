"""Train-only converged logistic head with fixed positive L2 regularization."""
import math
import torch


def fit_logistic(features, labels, weights, penalty=1.0):
    if type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:
        raise ValueError('Logistic penalty must be finite and positive')
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    y=torch.as_tensor(labels,dtype=torch.float64,device='cpu')
    mass=torch.as_tensor(weights,dtype=torch.float64,device='cpu')
    if x.ndim!=2 or x.shape[1]==0 or y.shape!=(len(x),) or mass.shape!=y.shape:
        raise ValueError('Logistic feature/target/weight shapes differ')
    if not torch.isfinite(mass).all() or (mass<0).any():
        raise ValueError('Logistic weights must be finite and nonnegative')
    known=mass>0;x,y,mass=x[known],y[known],mass[known]
    if (not len(x) or not torch.isfinite(x).all() or not ((y==0)|(y==1)).all()
            or len(torch.unique(y))!=2 or not torch.isfinite(mass.sum())):
        raise ValueError('Logistic requires finite training features and both binary classes')
    mass=mass/mass.sum()
    mean=(x*mass[:,None]).sum(0);x=x-mean
    weight=torch.zeros(x.shape[1],dtype=x.dtype,requires_grad=True)
    bias=torch.zeros((),dtype=x.dtype,requires_grad=True)
    optimizer=torch.optim.LBFGS([weight,bias],max_iter=100,tolerance_grad=1e-7,
        tolerance_change=1e-12,history_size=20,line_search_fn='strong_wolfe')
    evaluations=0
    def closure():
        nonlocal evaluations
        optimizer.zero_grad()
        loss=(torch.nn.functional.binary_cross_entropy_with_logits(x@weight+bias,y,reduction='none')*mass).sum()+.5*penalty*weight.square().sum()
        if not torch.isfinite(loss):raise ValueError('Non-finite logistic objective')
        loss.backward();evaluations+=1
        return loss
    optimizer.step(closure)
    objective=float(closure().detach())
    gradient=max(float(weight.grad.abs().max()),float(bias.grad.abs()))
    if not math.isfinite(gradient) or gradient>1e-5:
        raise ValueError('Logistic fit did not converge on training objective')
    coef=weight.detach().float();intercept=(bias.detach()-mean@weight.detach()).float()
    if not torch.isfinite(coef).all() or not torch.isfinite(intercept):
        raise ValueError('Non-finite logistic fit')
    return coef,intercept,dict(train_objective=objective,max_gradient=gradient,
        objective_evaluations=evaluations,fit_rows=len(x),converged=True)
