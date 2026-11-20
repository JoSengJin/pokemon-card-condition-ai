import json, sys, math
from collections import defaultdict
import numpy as np
G=json.load(open(sys.argv[2])); o=json.load(open(sys.argv[1])); out=sys.argv[3]
PM=set(range(3,16))|{17,19,20,21,22}|set(range(24,38))|{39,43,47,48,49,50,51,54,55,56,57,58,69,86,111}
GOLD={45,53,61,70,74,75,78,81,83,122,139,248,255,256}
lab={g['group']:('pm' if i in PM else 'gold' if i in GOLD else 'en') for i,g in enumerate(G)}
auto={g['group']:g['auto'] for g in G}
json.dump(dict(method='눈 확인(전체 사진 썸네일, Claude 2026-11-21), 사람 결함 라벨 아님',labels=lab),open(out,'w'),ensure_ascii=False,indent=0)
pm={k for k,v in lab.items() if v=='pm'}; a={k for k,v in auto.items() if v}
print('pm',len(pm),'gold',sum(v=='gold' for v in lab.values()),'auto',len(a),'TP',len(pm&a),'auto-only',len(a-pm),'missed by auto',len(pm-a))
z=1.6448536269514722
def wil(k,n):
    if n==0: return None
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return round((c+h)/d,3)
R,S=o['rows'],np.array(o['scores']); g=defaultdict(list)
for r,s in zip(R,S): g[r['group']].append((r['target'],s))
res=defaultdict(lambda:[0,0,0,0]); zs=defaultdict(lambda:[[],[]])
for k,v in g.items():
    c=lab[k]; x=res[c]
    if any(t for t,_ in v): x[0]+=any(t and s<0.281 for t,s in v); x[1]+=1
    else: x[2]+=any(s>=0.509 for _,s in v); x[3]+=1
    for t,s in v: zs[c][t].append(s)
for c,(m,P,f,N) in res.items():
    n0,n1=np.array(zs[c][0]),np.array(zs[c][1])
    auc=np.mean([(a>b)+0.5*(a==b) for a in n1 for b in n0]) if len(n0) and len(n1) else None
    print(c,'miss',m,P,'FA',f,N,'| normal zones',len(n0),'>=HIGH',int((n0>=0.509).sum()),'median',np.median(n0).round(3),'| defect zones',len(n1),'<LOW',int((n1<0.281).sum()),'| AUC',None if auc is None else round(auc,3))
# Fisher exact one-sided for FA pm vs rest
from math import comb
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    return sum(comb(r1,k)*comb(n-r1,c1-k)/comb(n,c1) for k in range(a,min(r1,c1)+1))
m,P,f,N=res['pm']; rest=[sum(res[c][i] for c in res if c!='pm') for i in range(4)]
print('FA pm vs rest fisher p(one-sided)',round(fisher(f,N-f,rest[2],rest[3]-rest[2]),4))
