"""Diagnosis only: card outer-edge vs box edge (slack), tilt, v2 error. Dev 36 fronts. Outer edge = strongest gradient within +-6% box height of the box edge, on three column bands."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
sys.path.insert(0, 'artifacts/centering-tb-measurer-v2-20261103'); import worker as W
D = Path('artifacts/centering-tb-diagnosis-20261103')
rows = json.loads(Path('artifacts/centering-tb-measurer-v2-20261103/rows.json').read_text())
k = np.exp(-.5*(np.arange(-8, 9)/2.0)**2); k /= k.sum()
def edge(g, x0, x1, side, bh, P):
    """slack>0: outer edge lies inside box by that fraction of box height; <0: outside. P=pad rows above/below box in g."""
    c = g[:, x0:x1].mean(1)
    if side == 'bot': c = c[::-1]
    gr = np.abs(np.gradient(np.convolve(c, k, 'same')))
    lim = min(int(.06*bh), P)
    seg = gr[P-lim:P+lim]
    return (P-lim+int(np.argmax(seg))-P)/bh

out = []
for i, r in enumerate(rows):
    im = ImageOps.exif_transpose(Image.open(r['image'])).convert('L'); w, h = im.size
    x0, y0, x1, y1 = r['box']; X0, Y0, X1, Y1 = round(x0*w), round(y0*h), round(x1*w), round(y1*h); bh, bw = Y1-Y0, X1-X0
    pad = min(int(.06*bh)+10, Y0, h-Y1)
    g = np.asarray(im, float)[Y0-pad:Y1+pad, X0:X1]
    res = {}
    for name, (a, b) in dict(L=(.15, .35), C=(.4, .6), R=(.65, .85)).items():
        res[name] = (edge(g, round(a*bw), round(b*bw), 'top', bh, pad), edge(g, round(a*bw), round(b*bw), 'bot', bh, pad))
    t, b = W.widths(r); ht, hb = r['human_top'], r['human_bottom']
    out.append(dict(i=i, target=r['target'], slack_top=res['C'][0], slack_bot=res['C'][1], tilt_top=res['R'][0]-res['L'][0], tilt_bot=res['R'][1]-res['L'][1],
        err=abs(abs(t-b)/(t+b)-abs(ht-hb)/(ht+hb)), v2_top=t, v2_bot=b, ht=ht, hb=hb))
    o = out[-1]; print('%2d %d slackT %+.3f slackB %+.3f tiltT %+.3f tiltB %+.3f err %.3f | v2-hum top %+.3f bot %+.3f' % (i, o['target'], o['slack_top'], o['slack_bot'], o['tilt_top'], o['tilt_bot'], o['err'], t-ht, b-hb))
json.dump(out, open(D/'slack.json', 'w'), indent=1)
def rk(v): return W.rank(np.array(v))
sl = [abs(o['slack_top'])+abs(o['slack_bot']) for o in out]; tl = [abs(o['tilt_top'])+abs(o['tilt_bot']) for o in out]; er = [o['err'] for o in out]
print('median |slack| top/bot %.3f %.3f ; p75 %.3f' % (np.median([abs(o['slack_top']) for o in out]), np.median([abs(o['slack_bot']) for o in out]), np.percentile([abs(o['slack_top']) for o in out]+[abs(o['slack_bot']) for o in out], 75)))
print('human width median', np.median([o['ht'] for o in out]+[o['hb'] for o in out]))
print('spearman err~slack %.3f  err~tilt %.3f' % (np.corrcoef(rk(er), rk(sl))[0, 1], np.corrcoef(rk(er), rk(tl))[0, 1]))
print('v2-width vs human width: corr top %.3f bot %.3f' % (np.corrcoef([o['v2_top'] for o in out], [o['ht'] for o in out])[0, 1], np.corrcoef([o['v2_bot'] for o in out], [o['hb'] for o in out])[0, 1]))
