import json, sys
from collections import defaultdict
import numpy as np
from PIL import Image
o=json.load(open(sys.argv[1])); R,S=o['rows'],np.array(o['scores']); T=np.array([r['target'] for r in R])
cache={}; red=[]; yel=[]
for r in R:
    if r['image'] not in cache: cache[r['image']]=np.asarray(Image.open(r['image']).convert('RGB')).astype(int)
    a=cache[r['image']]; H,W,_=a.shape; x0,y0,x1,y1=r['box']
    c=a[int(y0*H):int(np.ceil(y1*H)), int(x0*W):int(np.ceil(x1*W))]
    R_,G_,B_=c[...,0],c[...,1],c[...,2]
    red.append(((R_>150)&(G_<90)&(B_<110)).mean()); yel.append(((R_>200)&(G_>170)&(B_<90)).mean())
red=np.array(red); json.dump(red.tolist(),open(sys.argv[2],'w'))
print('red frac quantiles',np.quantile(red,[.5,.8,.9,.95,.99]).round(4))
for th in [0.003,0.005,0.01]:
    jp=red>=th
    # group-level: group is jp if any zone jp
    g=defaultdict(list)
    for r,j in zip(R,jp): g[r['group']].append(j)
    gj={k:np.mean(v)>=0.5 for k,v in g.items()}
    J=np.array([gj[r['group']] for r in R])
    def rate(m,base): return f"{(m&base).sum()}/{base.sum()}={((m&base).sum()/max(base.sum(),1)):.2f}"
    miss=(T==1)&(S<0.281); fa=(T==0)&(S>=0.509)
    print(th,'jp groups',sum(gj.values()),'zones',J.sum(),'| miss zone jp',rate(miss,(T==1)&J),'other',rate(miss,(T==1)&~J),'| FA zone jp',rate(fa,(T==0)&J),'other',rate(fa,(T==0)&~J),'| normal zone median score jp/other',np.median(S[(T==0)&J]).round(3),np.median(S[(T==0)&~J]).round(3), 'defect rate jp/other',T[J].mean().round(2),T[~J].mean().round(2))
