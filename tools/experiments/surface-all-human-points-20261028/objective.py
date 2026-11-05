"""Experiment only: average existing same-kind clicks within each unchanged positive bag."""
import math
import torch
from torch.nn import functional as F
from card_condition.detail_bag import detail_bag_loss
from card_condition.local_wear_cnn import point_input_pixel


def all_point_loss(logits,target,valid_mask,tokens,normal_reduction='max_bound'):
    unique=sorted(set(tokens))
    if any(type(t) is not int or not 0<=t<len(logits) or not valid_mask[t] for t in unique):
        raise ValueError('Human tokens must be inside the physical mask')
    if target==0 and unique:
        raise ValueError('Normal regions cannot contain defect point supervision')
    if not unique:
        return detail_bag_loss(logits,target,valid_mask,None,normal_reduction)
    if len(unique)==1:
        return detail_bag_loss(logits,target,valid_mask,unique[0],normal_reduction)
    return F.softplus(-logits[unique]).mean()


def existing_point_tokens(rows,masks,first,raw):
    by={r['id']:r for r in raw}
    result=[]
    for i,r in enumerate(rows):
        assert r['split']=='train'
        if r['target']==0:
            assert int(first[i])<0
            result.append([]);continue
        if r.get('card_id') not in by:
            # The two separately confirmed detail points already have their own frozen row.
            assert i>=147 and int(first[i])>=0 and r['point'].get('label',r.get('label'))=='surface_defect'
            result.append([int(first[i])]);continue
        original=by[r['card_id']];a=original['side_annotations'][r['side']]
        assert original['split']=='train' and not original.get('excluded',False)
        assert original.get('group',original['id'])==r['group']
        assert a['image']==r['image'] and a['box']==r['card_box']
        ts=[]
        for p in a.get('defect_points',[]):
            if p['label']!='surface_defect' or not (r['box'][0]<=p['x']<=r['box'][2] and r['box'][1]<=p['y']<=r['box'][3]):
                continue
            assert a['labels']['surface_defect']==1
            px,py=point_input_pixel(r['image'],r['box'],p)
            token=int(py//14)*16+int(px//14)
            assert masks[i,token]
            ts.append(token)
        assert (int(first[i]) in ts) if first[i]>=0 else not ts
        result.append(sorted(set(ts)))
    return result


def fit_all_point_head(features, masks, targets, point_tokens, weights, all_point_tokens, penalty=1.0, normal_reduction='mean_odds'):
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
    if len(all_point_tokens)!=len(x):
        raise ValueError('Aligned point lists required')
    for i,ts in enumerate(all_point_tokens):
        if ((points[i]>=0 and int(points[i]) not in ts) or (points[i]<0 and ts)
                or (y[i]==0 and ts)):
            raise ValueError('Existing first human token and positive kind must be preserved')
        all_point_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],ts,normal_reduction)
    all_point_tokens=[ts for i,ts in enumerate(all_point_tokens) if mass[i]>0]
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
        loss=sum(mass[i]*all_point_loss(logits[i],int(y[i]),valid[i],all_point_tokens[i],normal_reduction)
                 for i in range(len(x)))+.5*penalty*coef.square().sum()
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
        presence_positive_bags=int(((y==1)&(points<0)).sum()),
        unique_positive_tokens=sum(len(set(ts)) for ts in all_point_tokens),
        additional_positive_tokens=sum(max(0,len(set(ts))-1) for ts in all_point_tokens))
