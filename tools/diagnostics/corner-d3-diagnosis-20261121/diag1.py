import json, math, sys
from collections import defaultdict
import numpy as np
o=json.load(open(sys.argv[1]))
R,S,C=o['rows'],np.array(o['scores']),np.array(o['control_scores'])
T=np.array([r['target'] for r in R])
LOW,HIGH=0.281,0.509
z=1.6448536269514722
def wil(k,n):
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return (c+h)/d
def ev(sc,low=LOW,high=HIGH,unit='group'):
    g=defaultdict(list)
    for r,s in zip(R,sc): g[r[unit]].append((r['target'],s))
    pos=[v for v in g.values() if any(t for t,_ in v)]; neg=[v for v in g.values() if not any(t for t,_ in v)]
    m=sum(any(t and s<low for t,s in v) for v in pos); f=sum(any(s>=high for _,s in v) for v in neg)
    return m,len(pos),f,len(neg)
m,P,f,N=ev(S); print('L group',m,P,round(wil(m,P),3),f,N,round(wil(f,N),3))
print('control',ev(C))
print('L by image_sha',ev(S,unit='image_sha256'))
print('groups',len({r['group'] for r in R}),'images',len({r['image_sha256'] for r in R}))
print('pos zones',T.sum(),'neg',(1-T).sum())
print('def zone<LOW',(S[T==1]<LOW).sum(),(S[T==1]<LOW).mean().round(3),'q10 q30',np.quantile(S[T==1],[.1,.3]).round(3))
print('norm zone>=HIGH',(S[T==0]>=HIGH).sum(),(S[T==0]>=HIGH).mean().round(3))
g=defaultdict(list)
for r,s in zip(R,S): g[r['group']].append(r['target'])
pp=[v for v in g.values() if any(v)]; print('def zones per pos group mean',np.mean([sum(v) for v in pp]).round(2),'zones per group',np.mean([len(v) for v in g.values()]).round(2))
print('normal groups zones',np.mean([len(v) for v in g.values() if not any(v)]).round(2))
# implied by independence
p=(S[T==1]<LOW).mean(); print('indep implied miss', np.mean([1-(1-p)**sum(v) for v in pp]).round(3))
print('--- low sweep')
for low in [.281,.25,.2,.15,.12,.11,.10,.08]:
    m,P,_,_=ev(S,low=low); print(low,m,P,round(wil(m,P),3),'normal-zone low frac',(S[T==0]<low).mean().round(3),'def-zone low frac',(S[T==1]<low).mean().round(3), 'low-bin defect rate', round(T[S<low].mean(),3) if (S<low).any() else None)
print('--- high sweep')
for high in [.509,.6,.65,.7,.75,.8]:
    _,_,f,N=ev(S,high=high); print(high,f,N,round(wil(f,N),3),'def-zone high frac',(S[T==1]>=high).mean().round(3),'high-bin defect rate',round(T[S>=high].mean(),3))
# required counts
for n,lim in [(176,.10),(81,.20),(72,.10),(56,.20)]:
    k=max(k for k in range(n) if wil(k,n)<=lim); print('max k',n,lim,k)
