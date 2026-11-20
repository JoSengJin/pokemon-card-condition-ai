import json, sys
import numpy as np
from PIL import Image, ImageDraw
o=json.load(open(sys.argv[1])); ids=json.load(open(sys.argv[2]))
R,S=o['rows'],o['scores']; idx={r['id']:i for i,r in enumerate(R)}
out=sys.argv[3]
gpos={}
for r in R: gpos[r['group']]=gpos.get(r['group'],0)|r['target']
def sheet(lst,name,tile=260,cols=6):
    rows=(len(lst)+cols-1)//cols
    canvas=Image.new('RGB',(cols*tile,rows*(tile+30)),'white'); d=ImageDraw.Draw(canvas)
    for k,i in enumerate(lst):
        r=R[i]; im=Image.open(r['image']).convert('RGB'); W,H=im.size
        x0,y0,x1,y1=r['box']; c=im.crop((int(x0*W),int(y0*H),int(np.ceil(x1*W)),int(np.ceil(y1*H))))
        c.thumbnail((tile,tile)); X=(k%cols)*tile; Y=(k//cols)*(tile+30)
        canvas.paste(c,(X,Y)); d.text((X+2,Y+tile+2),f"{k}:{r['group']} {r['area'][:7]} {S[i]:.2f}",fill='black')
    canvas.save(f"{out}/{name}.png")
miss=sorted([idx[i] for i in ids['miss']],key=lambda i:S[i])
fa=sorted([idx[i] for i in ids['fa'] if not gpos[R[idx[i]]['group']]],key=lambda i:-S[i])
sheet(miss[:21],'miss_a'); sheet(miss[21:],'miss_b'); sheet(fa,'fa_normalcards')
# reference: high-score defect zones for comparison
hi=sorted([i for i,r in enumerate(R) if r['target']==1],key=lambda i:-S[i])[:12]; sheet(hi,'defect_top')
print(len(miss),len(fa))
