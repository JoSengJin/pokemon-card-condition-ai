"""D3 operating-point feasibility per supported back cell on frozen candidates' dev OOF scores. Read-only, no inference."""
import json, math, sys
from collections import defaultdict
import numpy as np
Z=1.6448536269514722
CELLS={'edge_C1':('20261104T133518-6303ee9c','vits14_scores',.31,.54),
       'corner_C2':('20261102T140143-82781117','scores',.281,.509),
       'surface_C3':('20261102T044321-8b790c22','scores',.213,.468),
       'obslimit_C5':('20261102T225059-98b83ef4','scores',.5,.5)}
def ub(k,n):
    if n==0: return None
    p=k/n; d=1+Z*Z/n; c=p+Z*Z/(2*n); h=Z*math.sqrt(p*(1-p)/n+Z*Z/(4*n*n)); return (c+h)/d
def need(k,n,lim):
    p=k/n
    return next((m for m in range(5,5000) if ub(round(p*m),m)<=lim),None)
def events(G,lo,hi,card):
    pos=[v for v in G.values() if any(t for t,_ in v)]; neg=[v for v in G.values() if not any(t for t,_ in v)]
    m=sum((all(s<lo for t,s in v if t) if card else any(t and s<lo for t,s in v)) for v in pos)
    f=sum(any(s>=hi for _,s in v) for v in neg); return m,len(pos),f,len(neg)
def cell(eid,key,lo0,hi0):
    o=json.load(open(f'artifacts/experiments/{eid}/observations.json')); S=np.array(o[key],float); T=np.array([r['target'] for r in o['rows']])
    G=defaultdict(list)
    for r,s in zip(o['rows'],S): G[r['group']].append((r['target'],s))
    grid=np.round(np.arange(.01,.99,.01),2); out=dict(zones=len(S),objects=len(G))
    m,P,f,N=events(G,lo0,hi0,False); out['frozen_L']=dict(lo=lo0,hi=hi0,miss=f'{m}/{P}',miss_ub=round(ub(m,P),3),fa=f'{f}/{N}',fa_ub=round(ub(f,N),3) if N else None,mid=round(float(((S>=lo0)&(S<hi0)).mean()),3))
    # rule (declared before looking at per-cell results): largest lo with card-level miss ub<=0.10; smallest hi with fa ub<=0.20
    los=[l for l in grid if events(G,l,1.1,True)[1] and ub(*events(G,l,1.1,True)[:2])<=.10]
    his=[h for h in grid if ub(*events(G,0,h,True)[2:])<=.20]
    lo=max(los) if los else None; hi=min(his) if his else None
    r=dict(lo=lo,hi=hi)
    if lo is not None and hi is not None:
        m,P,f,N=events(G,lo,hi,True); mid=((S>=lo)&(S<hi)).mean() if lo<hi else 0.0
        r.update(miss=f'{m}/{P}',miss_ub=round(ub(m,P),3),fa=f'{f}/{N}',fa_ub=round(ub(f,N),3),mid=round(float(mid),3),
                 lowbin_defect=round(float(T[S<lo].mean()),3) if (S<lo).any() else None,highbin_defect=round(float(T[S>=hi].mean()),3),
                 lowbin_share=round(float((S<lo).mean()),3),highbin_share=round(float((S>=hi).mean()),3),
                 crossed=bool(lo>=hi),need_pos=need(m,P,.10) if m else 25,need_neg=need(f,N,.20) if f else 11)
    out['rule_card']=r; return out
res={k:cell(*v) for k,v in CELLS.items()}
json.dump(res,open(sys.argv[1],'w'),ensure_ascii=False,indent=1); print(json.dumps(res,ensure_ascii=False,indent=1))
