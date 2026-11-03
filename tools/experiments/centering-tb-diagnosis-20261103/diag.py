"""C4 diagnosis only (no learning, no new measurer): box slack vs card outer edge, v2 error, boundary type. Dev 36 fronts."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageDraw
sys.path.insert(0, 'artifacts/centering-tb-measurer-v2-20261103')
import worker as W
OUT = Path('artifacts/centering-tb-diagnosis-20261103'); (OUT/'img').mkdir(exist_ok=True)
rows = json.loads(Path('artifacts/centering-tb-measurer-v2-20261103/rows.json').read_text())
res = []
for i, r in enumerate(rows):
    im = ImageOps.exif_transpose(Image.open(r['image'])).convert('RGB'); w, h = im.size
    x0, y0, x1, y1 = r['box']; X0, Y0, X1, Y1 = round(x0*w), round(y0*h), round(x1*w), round(y1*h)
    g = np.asarray(im.convert('L'), float)[Y0:Y1, X0:X1]; bh, bw = g.shape
    col = g[:, round(.25*bw):round(.75*bw)].mean(1)
    k = np.exp(-.5*(np.arange(-8, 9)/2.0)**2); sm = np.convolve(col, k/k.sum(), 'same'); gr = np.abs(np.gradient(sm))
    def edges(side):
        a = gr if side == 'top' else gr[::-1]
        n = len(a); lim = int(.15*n)
        pk = [j for j in range(2, lim) if a[j] >= a[j-1] and a[j] >= a[j+1] and a[j] > .5*a[:lim].max()]
        return pk, n
    tp, n = edges('top'); bp, _ = edges('bot')
    t, b = W.widths(r)
    res.append(dict(id=r['id'], target=r['target'], bh=bh, bw=bw, top_peaks=[p/n for p in tp], bot_peaks=[p/n for p in bp], v2=(t, b), human=(r['human_top'], r['human_bottom'])))
    d = ImageDraw.Draw(im); d.rectangle([X0, Y0, X1, Y1], outline=(255, 255, 0), width=4)
    for f, c, side in ((r['human_top'], (0, 255, 0), 't'), (t, (255, 0, 0), 't')):
        y = Y0+f*bh; d.line([X0, y, X1, y], fill=c, width=3)
    for f, c in ((r['human_bottom'], (0, 255, 0)), (b, (255, 0, 0))):
        y = Y1-f*bh; d.line([X0, y, X1, y], fill=c, width=3)
    for p in tp: d.line([X0, Y0+p*bh, X0+40, Y0+p*bh], fill=(0, 128, 255), width=3)
    for p in bp: d.line([X0, Y1-p*bh, X0+40, Y1-p*bh], fill=(0, 128, 255), width=3)
    im.crop((X0-30, Y0-30, X1+30, Y1+30)).resize((420, int(420*(Y1-Y0+60)/(X1-X0+60)))).save(OUT/'img'/f'{i:02d}.jpg', quality=80)
json.dump(res, open(OUT/'diag.json', 'w'), indent=1)
for i, x in enumerate(res):
    print(i, x['target'], 'hum %.3f/%.3f v2 %.3f/%.3f' % (*x['human'], *x['v2']), 'topPk', [round(p, 3) for p in x['top_peaks']], 'botPk', [round(p, 3) for p in x['bot_peaks']])
