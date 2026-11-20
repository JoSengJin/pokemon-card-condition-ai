import json, sys
from collections import defaultdict, Counter
import numpy as np
from PIL import Image
o=json.load(open(sys.argv[1]))
R,S=o['rows'],np.array(o['scores']); T=np.array([r['target'] for r in R])
LOW,HIGH=0.281,0.509
size={}
for r in R:
    if r['image'] not in size:
        try: size[r['image']]=Image.open(r['image']).size
        except Exception as e: size[r['image']]=None
W=np.array([size[r['image']][0] if size[r['image']] else np.nan for r in R])
H=np.array([size[r['image']][1] if size[r['image']] else np.nan for r in R])
CW=np.array([(r['box'][2]-r['box'][0])*W[i] for i,r in enumerate(R)])
CH=np.array([(r['box'][3]-r['box'][1])*H[i] for i,r in enumerate(R)])
print('missing images',sum(v is None for v in size.values()))
A=np.array([r['area'] for r in R]); G=np.array([r['group'] for r in R]); SRC=np.array([r['group'][:1] for r in R])
gpos=defaultdict(int)
for r in R: gpos[r['group']]|=r['target']
GP=np.array([gpos[g] for g in G])
def tab(mask,base,name,keyarr):
    c=Counter(keyarr[mask]); b=Counter(keyarr[base])
    print(name,{k:f"{c[k]}/{b[k]}={c[k]/b[k]:.2f}" for k in sorted(b)})
miss=(T==1)&(S<LOW); fa=(T==0)&(S>=HIGH)
tab(miss,T==1,'miss by area',A); tab(fa,T==0,'FA-zone by area',A)
cwb=np.digitize(CW,[200,300,400]); tab(miss,T==1,'miss by cropW bin(<200,<300,<400,>=400)',cwb); tab(fa,T==0,'FA by cropW bin',cwb)
wb=np.digitize(W,[1000,1500]); tab(miss,T==1,'miss by imgW(<1000,<1500,>=1500)',wb); tab(fa,T==0,'FA by imgW',wb)
tab(fa,T==0,'FA-zone by group has defect',GP)
print('crop w median def/norm',np.nanmedian(CW[T==1]).round(),np.nanmedian(CW[T==0]).round())
# missed zones: does same group have another defect zone scored high?
mg=set(G[miss]); 
sib=[ (S[(G==g)&(T==1)&~miss]).max() if ((G==g)&(T==1)&~miss).any() else None for g in mg]
print('missed groups',len(mg),'with another defect zone >=HIGH',sum(1 for s in sib if s is not None and s>=HIGH),'no other defect zone',sum(1 for s in sib if s is None))
print('missed zone score quantiles',np.quantile(S[miss],[0,.25,.5,.75,1]).round(3))
# groups missed only due to one zone
cnt=Counter(G[miss]); print('missed zones per missed group',Counter(cnt.values()))
# split / fold info
print('split counts miss',Counter(np.array([r['split'] for r in R])[miss]))
print('group prefix miss',Counter(SRC[miss]).most_common(8),'base',Counter(SRC[T==1]).most_common(8))
print('FA groups (normal) count',len(set(G[fa&(GP==0)])))
json.dump({'miss':[R[i]['id'] for i in np.where(miss)[0]],'fa':[R[i]['id'] for i in np.where(fa)[0]]},open(sys.argv[2],'w'))
