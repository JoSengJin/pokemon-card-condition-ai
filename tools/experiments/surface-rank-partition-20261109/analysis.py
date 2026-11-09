"""Exact saved-score pair partition; no models, fitting or score transforms."""
import numpy as np


def validate(rows,scores,folds):
    if not rows or len(scores)!=len(rows) or len({r['id'] for r in rows})!=len(rows):
        raise ValueError('Nonempty unique rows and matching scores required')
    values=np.asarray(scores,dtype=float)
    if values.shape!=(len(rows),) or not np.isfinite(values).all() or ((values<0)|(values>1)).any():
        raise ValueError('Finite saved probability scores required')
    images={};groups={}
    for r in rows:
        if type(r['target']) is not int or r['target'] not in (0,1) or r['group'] not in folds or type(folds[r['group']]) is not int:
            raise ValueError('Explicit binary truth and known integer fold required')
        if r['image_sha256'] in images and images[r['image_sha256']]!=r['group']:
            raise ValueError('A photo cannot span physical/photo groups')
        if r['group'] in groups and groups[r['group']]!=(r['image_sha256'],r['image']):
            raise ValueError('One-photo group identity required')
        images[r['image_sha256']]=r['group'];groups[r['group']]=(r['image_sha256'],r['image'])
        box=np.asarray(r['box'],dtype=float)
        if box.shape!=(4,) or not np.isfinite(box).all() or (box<0).any() or (box>1).any() or box[0]>=box[2] or box[1]>=box[3]:
            raise ValueError('Normalized nonempty region box required')
    if len({r['target'] for r in rows})!=2:raise ValueError('Both classes required')
    return values


def partition(rows,scores,folds):
    values=validate(rows,scores,folds)
    positive=np.array([i for i,r in enumerate(rows) if r['target']==1]);negative=np.array([i for i,r in enumerate(rows) if r['target']==0])
    same=np.array([[rows[i]['group']==rows[j]['group'] for j in negative] for i in positive])
    same_fold=np.array([[folds[rows[i]['group']]==folds[rows[j]['group']] for j in negative] for i in positive])
    margin=values[negative][None,:]-values[positive][:,None]
    inverted=margin>0;tie=margin==0
    masks=[same,(~same)&same_fold,~same_fold]
    if not np.all(sum(mask.astype(int) for mask in masks)==1):raise ValueError('Partition is not exhaustive/disjoint')
    buckets=[];examples=[]
    for key,mask in zip(('same_photo','cross_photo_same_fold','cross_fold'),masks):
        count=int(mask.sum());wrong=int((mask&inverted).sum());ties=int((mask&tie).sum());credit=wrong+ties/2
        buckets.append(dict(key=key,pairs=count,strict_inversions=wrong,ties=ties,error_credit=credit,auc=1-credit/count if count else None,loss_share=0.))
        pairs=np.argwhere(mask&inverted)
        selected=sorted(pairs.tolist(),key=lambda pair:(-margin[pair[0],pair[1]],rows[positive[pair[0]]]['id'],rows[negative[pair[1]]]['id']))[:5]
        for pi,ni in selected:
            i,j=int(positive[pi]),int(negative[ni])
            examples.append(dict(bucket=key,defect_id=rows[i]['id'],normal_id=rows[j]['id'],defect_score=float(values[i]),normal_score=float(values[j]),normal_minus_defect=float(margin[pi,ni])))
    count=len(positive)*len(negative);wrong=int(inverted.sum());ties=int(tie.sum());credit=wrong+ties/2
    total=dict(pairs=count,strict_inversions=wrong,ties=ties,error_credit=credit,auc=1-credit/count,loss_share=1. if credit else 0.)
    for key in ('pairs','strict_inversions','ties','error_credit'):
        if sum(b[key] for b in buckets)!=total[key]:raise ValueError('Partition identity failed')
    for b in buckets:b['loss_share']=b['error_credit']/credit if credit else 0.
    return total,buckets,examples


def photos(rows,scores,folds):
    groups={}
    for r,s in zip(rows,scores):
        group=r['group'];prediction=int(s>=.5);target=r['target']
        outcome=('TP' if prediction else 'FN') if target else ('FP' if prediction else 'TN')
        groups.setdefault(group,dict(group=group,fold=folds[group],image=r['image'],image_sha256=r['image_sha256'],zones=[]))
        groups[group]['zones'].append(dict(id=r['id'],area=r['area'],box=r['box'],target=target,score=float(s),prediction=prediction,outcome=outcome))
    return list(groups.values())
