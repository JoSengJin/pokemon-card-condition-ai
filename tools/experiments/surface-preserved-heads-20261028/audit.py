"""Compare fixed training/held behavior; no optimizer and no post-hoc role selection."""
import torch
from card_condition.detail_bag import detail_bag_loss


def readout(x,head,kind,features,mask):
    if kind=='preserved':x=features.preserved_features(x,mask)
    prefix='point_' if kind=='point_role' else 'presence_' if kind=='presence_role' else ''
    return (x@head[prefix+'coef']+head[prefix+'bias']).sigmoid()


def counts(rows,first,maps,mask):
    score=maps.masked_fill(~mask,-1).max(1).values
    positive=[i for i,r in enumerate(rows) if r['target']==1];normal=[i for i,r in enumerate(rows) if r['target']==0];actual=[i for i in positive if first[i]>=0];weak=[i for i in positive if first[i]<0]
    return dict(fn=sum(float(score[i])<.5 for i in positive),positives=len(positive),fp=sum(float(score[i])>=.5 for i in normal),negatives=len(normal),point_fn=sum(float(maps[i,int(first[i])])<.5 for i in actual),points=len(actual),weak_fn=sum(float(score[i])<.5 for i in weak),weak_positives=len(weak))


def objective(x,mask,first,rows,mass,coef,bias):
    z=x.double()@coef.double()+float(bias);mass=mass.double()/mass.double().sum()
    return float(sum(mass[i]*detail_bag_loss(z[i],r['target'],mask[i],None if first[i]<0 else int(first[i]),'max_bound') for i,r in enumerate(rows))+.5*coef.double().square().sum())


def audit_fold(ctx,fold,states,features,balanced,reference_fits):
    fold_id,train,held=fold;heads={name:next(h for h in state['heads'] if h['fold']==fold_id) for name,state in states.items()}
    rows=[ctx['all_rows'][i] for i in train]
    assert all(h['train_ids']==[r['id'] for r in rows] for h in heads.values())
    assert heads['separated']['point_train_ids']==[ctx['all_rows'][i]['id'] for i in train if ctx['all_rows'][i]['target']==0 or ctx['tokens'][i]>=0]
    result=dict(fold=fold_id,models={},max_held_map_error=0.)
    for kind in ('baseline','preserved','separated','point_role','presence_role'):
        head=heads['separated'] if kind in ('point_role','presence_role') else heads[kind];parts={}
        for part,indices in (('training_common_truth',train),('held',held)):
            values=readout(ctx['x'][indices],head,kind,features,ctx['masks'][indices]);selected=[ctx['all_rows'][i] for i in indices]
            parts[part]=counts(selected,ctx['tokens'][indices],values,ctx['masks'][indices])
            if part=='held' and kind in states:
                error=float((values-states[kind]['maps'][indices]).abs().max());assert error<=2e-5;result['max_held_map_error']=max(result['max_held_map_error'],error)
        result['models'][kind]=parts
    _,mass=balanced(rows);x=ctx['x'][train];mask=ctx['masks'][train];tokens=ctx['tokens'][train];expanded=features.preserved_features(x,mask);old=heads['baseline'];new=heads['preserved']
    embedded=torch.cat((old['coef'],torch.zeros_like(old['coef'])))
    original=objective(x,mask,tokens,rows,mass,old['coef'],old['bias']);control=objective(expanded,mask,tokens,rows,mass,embedded,old['bias']);candidate=objective(expanded,mask,tokens,rows,mass,new['coef'],new['bias'])
    assert abs(original-control)<=2e-5
    assert abs(original-reference_fits['baseline'][fold_id])<=2e-5 and abs(candidate-reference_fits['preserved'][fold_id])<=2e-5
    result['objective_certificate']=dict(original=original,embedded_original=control,preserved=candidate,embedding_error=abs(original-control),candidate_minus_embedded=candidate-control)
    return result


def run_audit(ctx,folds,states,features,balanced,reference_fits):
    with torch.inference_mode():results=[audit_fold(ctx,fold,states,features,balanced,reference_fits) for fold in folds]
    return dict(folds=results,new_fits=0,new_backbone_forwards=0,cached_head_projections=40,training_rows_repeated_across_folds=True,role_heads_not_selected=True)
