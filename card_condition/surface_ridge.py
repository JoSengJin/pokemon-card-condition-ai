"""Deterministic weighted linear fit; callers give held-out rows zero weight."""
import math
import torch


def fit_ridge(features, labels, weights, penalty=1.0):
    if type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:
        raise ValueError('Ridge penalty must be finite and positive')
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    y=torch.as_tensor(labels,dtype=torch.float64,device='cpu')
    w=torch.as_tensor(weights,dtype=torch.float64,device='cpu')
    if x.ndim!=2 or x.shape[1]==0 or y.shape!=(len(x),) or w.shape!=y.shape:
        raise ValueError('Ridge feature/target/weight shapes differ')
    if not torch.isfinite(w).all() or (w<0).any():
        raise ValueError('Ridge weights must be finite and nonnegative')
    known=w>0;x,y,w=x[known],y[known],w[known]
    if (not len(x) or not torch.isfinite(x).all() or not ((y==0)|(y==1)).all()
            or len(torch.unique(y))!=2 or not torch.isfinite(w.sum())):
        raise ValueError('Ridge requires finite training features and both binary classes')
    w=w/w.sum();y=2*y-1
    mean_x=(x*w[:,None]).sum(0);mean_y=(y*w).sum()
    centered=x-mean_x;root=w.sqrt();z=centered*root[:,None]
    dual=torch.linalg.solve(z@z.T+penalty*torch.eye(len(x),dtype=x.dtype),root*(y-mean_y))
    weight=z.T@dual;bias=mean_y-mean_x@weight
    weight,bias=weight.float(),bias.float()
    if not torch.isfinite(weight).all() or not torch.isfinite(bias):
        raise ValueError('Non-finite ridge fit')
    return weight,bias
