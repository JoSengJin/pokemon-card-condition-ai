"""Independent nested-loop pair oracle on synthetic rows only."""
import ast
from pathlib import Path
import sys
import math
import random

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from analysis import partition,photos


def row(i,target,group):
    return dict(id=str(i),target=target,group=group,image=group+'.jpg',image_sha256=group,area='synthetic',box=[0.,0.,1.,1.])


def oracle(rows,scores,folds):
    counts={k:[0,0,0] for k in ('same_photo','cross_photo_same_fold','cross_fold')}
    for i,p in enumerate(rows):
        if not p['target']:continue
        for j,n in enumerate(rows):
            if n['target']:continue
            key='same_photo' if p['group']==n['group'] else 'cross_photo_same_fold' if folds[p['group']]==folds[n['group']] else 'cross_fold'
            counts[key][0]+=1;counts[key][1]+=scores[i]<scores[j];counts[key][2]+=scores[i]==scores[j]
    return counts


if __name__=='__main__':
    rng=random.Random(20261109)
    for case in range(30):
        rows=[row(i,i%2,'g'+str(i%7)) for i in range(25)];scores=[rng.choice([0.,.1,.5,.9,1.]) for r in rows];folds={'g'+str(i):i%3 for i in range(7)}
        total,buckets,examples=partition(rows,scores,folds);expected=oracle(rows,scores,folds)
        for b in buckets:
            pairs,wrong,ties=expected[b['key']]
            assert [b['pairs'],b['strict_inversions'],b['ties']]==[pairs,wrong,ties]
            assert b['error_credit']==wrong+ties*.5 and b['auc']==(1-(wrong+.5*ties)/pairs if pairs else None)
        assert total['pairs']==156 and total['auc']==1-total['error_credit']/156
        order=list(range(len(rows)));rng.shuffle(order)
        p2,b2,e2=partition([rows[i] for i in order],[scores[i] for i in order],folds)
        assert (total,buckets,examples)==(p2,b2,e2)
        assert sum(len(p['zones']) for p in photos(rows,scores,folds))==25
    simple=[row(0,1,'g'),row(1,0,'g')]
    t,b,e=partition(simple,[.5,.5],{'g':0});assert t['auc']==.5 and t['ties']==1 and all(v['auc'] is None for v in b[1:])
    t,b,e=partition(simple,[1.,0.],{'g':0});assert t['auc']==1. and all(v['loss_share']==0 for v in b)
    for rows,scores,folds in [(simple,[float('nan'),.5],{'g':0}),(simple,[.1,1.1],{'g':0}),(simple,[.1,.5],{}),([simple[0],simple[0]],[.1,.5],{'g':0})]:
        try:partition(rows,scores,folds)
        except ValueError:pass
        else:raise AssertionError('Invalid inputs accepted')
    rounded=[row(0,1,'g'),row(1,0,'g')];rounded[0]['box'][3]=1.0000000000000002
    assert partition(rounded,[.5,.5],{'g':0})[0]['auc']==.5
    rounded[0]['box'][3]=1.01
    try:partition(rounded,[.5,.5],{'g':0})
    except ValueError:pass
    else:raise AssertionError('Out-of-range box accepted')
    bad=[row(0,1,'a'),row(1,0,'b')];bad[1]['image_sha256']='a'
    try:partition(bad,[.1,.5],{'a':0,'b':1})
    except ValueError:pass
    else:raise AssertionError('Photo/group overlap accepted')
    counts={p.name:sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(p.read_text()))) for p in HERE.glob('*.py')}
    assert max(counts.values())<=7
    print('PASS:30 independent nested-loop oracle cases, ties/empty/zero-error buckets, permutation/example stability, photo schema, invalid scores/identity/folds, AST',counts)
