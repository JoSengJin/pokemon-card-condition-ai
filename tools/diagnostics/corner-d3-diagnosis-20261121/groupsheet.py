import json, sys
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw
o=json.load(open(sys.argv[1])); red=json.load(open(sys.argv[2])); out=sys.argv[3]
R=o['rows']; g=defaultdict(list)
for r,x in zip(R,red): g[r['group']].append((r,x))
items=[]
for k,v in g.items():
    jp=np.mean([x>=0.005 for _,x in v])>=0.5
    items.append((k,v[0][0]['image'],round(float(np.mean([x for _,x in v])),4),jp,any(r['target'] for r,_ in v)))
items.sort(key=lambda t:-t[2])
json.dump([dict(group=k,image=i,red=x,auto=bool(j),pos=bool(p)) for k,i,x,j,p in items],open(f'{out}/groups.json','w'),ensure_ascii=False)
tile,cols=170,10
for s in range(0,len(items),60):
    chunk=items[s:s+60]; rows=(len(chunk)+cols-1)//cols
    c=Image.new('RGB',(cols*tile,rows*(tile+16)),'white'); d=ImageDraw.Draw(c)
    for n,(k,img,x,j,p) in enumerate(chunk):
        im=Image.open(img).convert('RGB'); im.thumbnail((tile,tile)); X=(n%cols)*tile; Y=(n//cols)*(tile+16)
        c.paste(im,(X,Y)); d.text((X+2,Y+tile+1),f"{s+n} {'J' if j else '-'} {x:.3f}",fill='red' if j else 'black')
    c.save(f'{out}/groups_{s//60}.png')
print(len(items), sum(t[3] for t in items))
