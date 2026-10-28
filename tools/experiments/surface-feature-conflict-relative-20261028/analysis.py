"""Frozen feature overlap and loss-gradient diagnostics; no optimizer."""
import itertools
import torch


def components(x,mask,w0,b0,w1,b1):
    x=x.double();w0=w0.double();w1=w1.double();mean=x[mask].mean(0)
    z0=x@w0+float(b0);z1=x@w1+float(b1)
    p0=int(z0.masked_fill(~mask,-torch.inf).argmax());p1=int(z1.masked_fill(~mask,-torch.inf).argmax())
    common=float(mean@(w1-w0)+float(b1)-float(b0))
    residual=float((x[p0]-mean)@(w1-w0));peak=float((x[p1]-x[p0])@w1)
    delta=float(z1[p1]-z0[p0]);error=abs(delta-common-residual-peak)
    assert error<=1e-8
    return dict(common_delta=common,residual_delta=residual,peak_relocation=peak,delta_logit=delta,additive_error=error,old_peak=p0,new_peak=p1)


def neighbors(x,masks,rows,points,query,relative=False):
    positive=[];normal=[];pmeta=[];nmeta=[]
    for i,r in enumerate(rows):
        values=x[i].double();mean=values[masks[i]].mean(0) if relative else 0
        if r['target']==1:
            for t in points[i]:positive.append(values[t]-mean);pmeta.append(dict(id=r['id'],group=r['group'],token=t))
        else:
            for t in masks[i].nonzero().flatten().tolist():normal.append(values[t]-mean);nmeta.append(dict(id=r['id'],group=r['group'],token=t))
    result={};q=query.double()/query.double().norm().clamp_min(1e-12)
    for name,pool,meta in (('human_points',positive,pmeta),('explicit_normal_tokens',normal,nmeta)):
        if not pool:result[name]=dict(pool_tokens=0,top=[]);continue
        matrix=torch.stack(pool);similarity=(matrix/matrix.norm(dim=1,keepdim=True).clamp_min(1e-12))@q
        values,index=similarity.topk(min(5,len(pool)))
        result[name]=dict(pool_tokens=len(pool),groups=len({r['group'] for r in meta}),top=[dict(meta[j],cosine=float(v)) for v,j in zip(values,index.tolist())])
    return result


def gradients(x,masks,first,mass,center,coef,bias,points,use_all,loss_for):
    w=coef.double().detach().clone().requires_grad_();b=torch.tensor(float(bias)+float(center@coef.double()),dtype=torch.float64,requires_grad=True)
    z=(x.double()-center)@w+b;zero=z.sum()*0
    losses=dict(point=zero,presence=zero,normal=zero,regularizer=.5*w.square().sum()+b*0)
    for i in range(len(x)):
        target=int(mass['targets'][i]);ts=points[i] if use_all else ([int(first[i])] if first[i]>=0 else [])
        kind='normal' if target==0 else 'point' if ts else 'presence'
        losses[kind]=losses[kind]+mass['weights'][i]*loss_for(z[i],target,masks[i],ts,'max_bound')
    vectors={}
    for name,value in losses.items():
        gw,gb=torch.autograd.grad(value,(w,b),retain_graph=True);vectors[name]=torch.cat((gw,gb[None]))
    gw,gb=torch.autograd.grad(sum(losses.values()),(w,b));whole=torch.cat((gw,gb[None]));error=float((sum(vectors.values())-whole).abs().max())
    assert error<=1e-10
    cosines={a+'/'+c:float(torch.nn.functional.cosine_similarity(vectors[a],vectors[c],dim=0,eps=1e-12)) for a,c in itertools.combinations(vectors,2)}
    return dict(losses={k:float(v.detach()) for k,v in losses.items()},norms={k:float(v.norm()) for k,v in vectors.items()},cosines=cosines,sum_error=error,total_gradient_max=float(whole.abs().max())),vectors


def diagnose(ctx,folds,old,new,points,loss_for,training_state):
    cases=[];losses=[];focus={9,21,42,46,60,69}
    for fold_id,train,held in folds:
        rows=[ctx['all_rows'][i] for i in train];x=ctx['x'][train];m=ctx['masks'][train];first=ctx['tokens'][train];ps=[points[i] for i in train]
        h0=next(h for h in old['heads'] if h['fold']==fold_id);h1=next(h for h in new['heads'] if h['fold']==fold_id)
        assert h0['train_ids']==h1['train_ids']==[r['id'] for r in rows]
        center,mass=training_state(x,m,first,rows);mass=dict(weights=mass,targets=[r['target'] for r in rows])
        first_info,first_g=gradients(x,m,first,mass,center,h0['coef'],h0['bias'],ps,False,loss_for)
        all_info,all_g=gradients(x,m,first,mass,center,h0['coef'],h0['bias'],ps,True,loss_for)
        final_info,final_g=gradients(x,m,first,mass,center,h1['coef'],h1['bias'],ps,True,loss_for)
        losses.append(dict(fold=fold_id,baseline_first=first_info,baseline_all=all_info,final_all=final_info))
        for i in held:
            row=ctx['rows'][i];f=components(ctx['x'][i],ctx['masks'][i],h0['coef'],h0['bias'],h1['coef'],h1['bias'])
            assert abs(float((ctx['x'][i]@h0['coef']+h0['bias']).sigmoid()[ctx['masks'][i]].max())-ctx['replay'][i])<2e-5
            result=dict(index=i,id=row['id'],fold=fold_id,target=row['target'],**f)
            if i in focus:
                peak=ctx['x'][i,f['new_peak']].double();mean=ctx['x'][i,ctx['masks'][i]].double().mean(0)
                result['neighbors_raw']=neighbors(x,m,rows,ps,peak)
                result['neighbors_relative']=neighbors(x,m,rows,ps,peak-mean,True)
                assert not {v['group'] for mode in ('neighbors_raw','neighbors_relative') for pool in result[mode].values() for v in pool['top']} & {row['group']}
                q=torch.cat((ctx['x'][i,f['old_peak']].double()-center,torch.ones(1,dtype=torch.float64)))
                result['gradient_query_peak']=f['old_peak']
                result['local_descent_by_term']={k:-float(q@g) for k,g in all_g.items()}
                result['extra_click_local_descent']=-float(q@(all_g['point']-first_g['point']))
            cases.append(result)
    assert len(cases)==91
    gate=any(r['index'] in (9,21) and r['common_delta']>0 and r['common_delta']>=.5*r['delta_logit'] for r in cases)
    return dict(cases=cases,fold_losses=losses,relative_input_evidence_gate=gate,new_fit=0,new_backbone_forward=0,causal_claim=False)
