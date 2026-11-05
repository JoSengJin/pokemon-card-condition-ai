"""Experiment-only same-photo exact-point / explicitly-normal ranking supervision."""
import math
import torch
from torch.nn import functional as F
from card_condition.detail_bag import detail_bag_loss


def training_pairs(rows, tokens):
    if len(rows)!=len(tokens):
        raise ValueError('Aligned source rows and point tokens are required')
    pairs=[]
    for i,row in enumerate(rows):
        if row['side']!='front' or row['target']!=1 or int(tokens[i])<0:
            continue
        point=row.get('point_by_label',{}).get('surface_defect',row.get('point'))
        if (not isinstance(point,dict) or point.get('label',row.get('label'))!='surface_defect'
                or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) for k in ('x','y'))):
            raise ValueError('Only an explicit correct-kind human point can form a ranking pair')
        normal=[]
        for j,other in enumerate(rows):
            if (other['side']!='front' or other['target']!=0
                    or (other['group'],other['image'])!=(row['group'],row['image'])):
                continue
            normal_truth=other.get('labels',{}).get('surface_defect',other['target'] if other.get('label')=='surface_defect' else None)
            if normal_truth!=0:
                raise ValueError('Same-photo normal needs explicit surface-normal truth')
            left,top,right,bottom=other['box']
            if left<=point['x']<=right and top<=point['y']<=bottom:
                raise ValueError('Human defect point contradicts the paired normal box')
            normal.append(j)
        if normal:
            pairs.append((i,tuple(normal)))
    return pairs


def same_photo_ranking_loss(logits, masks, tokens, mass, pairs):
    total=logits.sum()*0
    for i,normal in pairs:
        point=logits[i,int(tokens[i])]
        contrasts=torch.stack([F.softplus(1+.1*torch.logsumexp(logits[j,masks[j]]/.1,0)-point) for j in normal])
        total=total+mass[i]*contrasts.mean()
    return total


def fit_rank_head(features, masks, targets, point_tokens, weights, rows, penalty=1.0, normal_reduction='mean_odds'):
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
    if len(rows)!=len(x) or (mass<=0).any() or any(r['target']!=int(y[i]) for i,r in enumerate(rows)):
        raise ValueError('Aligned source rows and positive original mass are required')
    pairs=training_pairs(rows,points)
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
        loss=sum(mass[i]*detail_bag_loss(logits[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
                 for i in range(len(x)))+.5*penalty*coef.square().sum()
        loss=loss+same_photo_ranking_loss(logits,valid,points,mass,pairs)
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
        ranking_point_pairs=len(pairs),ranking_comparisons=sum(len(js) for _,js in pairs),
        point_positive_bags=int(((y==1)&(points>=0)).sum()),
        presence_positive_bags=int(((y==1)&(points<0)).sum()))
