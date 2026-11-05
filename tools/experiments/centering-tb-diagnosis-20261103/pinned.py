"""Diagnosis only: strips of the 22 v2 edges pinned at window bounds. Strip = first 9% of box height at the edge, 4x magnified; green=human mark, red=v2 pick, cyan=window bounds."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageDraw
sys.path.insert(0, 'artifacts/centering-tb-measurer-v2-20261103'); import worker as W
D = Path('artifacts/centering-tb-diagnosis-20261103')
rows = json.loads(Path('artifacts/centering-tb-measurer-v2-20261103/rows.json').read_text())
tiles, meta = [], []
for i, r in enumerate(rows):
    t, b = W.widths(r)
    im = ImageOps.exif_transpose(Image.open(r['image'])).convert('RGB'); w, h = im.size
    X0, Y0, X1, Y1 = round(r['box'][0]*w), round(r['box'][1]*h), round(r['box'][2]*w), round(r['box'][3]*h); bh = Y1-Y0
    for side, v, hm in (('top', t, r['human_top']), ('bot', b, r['human_bottom'])):
        if not (abs(v-.022) < .0015 or abs(v-.049) < .0015): continue
        n = int(.09*bh)
        strip = im.crop((X0+int(.3*(X1-X0)), Y0 if side == 'top' else Y1-n, X0+int(.7*(X1-X0)), (Y0+n) if side == 'top' else Y1))
        if side == 'bot': strip = strip.transpose(Image.FLIP_TOP_BOTTOM)   # outer edge always at y=0
        sc = 360/strip.width; strip = strip.resize((360, int(strip.height*sc))); d = ImageDraw.Draw(strip)
        for f, c in ((hm, (0, 255, 0)), (v, (255, 0, 0)), (.022, (0, 255, 255)), (.049, (0, 255, 255))):
            y = f*bh*sc; d.line([0, y, 360, y], fill=c, width=1)
        d.text((3, 3), f'#{i}{side} {"D" if r["target"] else "N"} h{hm:.3f} v{v:.3f}', fill=(255, 255, 255))
        tiles.append(strip); meta.append(dict(i=i, side=side, v2=v, human=hm, pin='lo' if abs(v-.022) < .0015 else 'hi'))
cols = 4; ch = max(t.height for t in tiles)+4
sheet = Image.new('RGB', (cols*364, ((len(tiles)+cols-1)//cols)*ch), 'black')
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols)*364, (k//cols)*ch))
sheet.save(D/'pinned_sheet.png'); json.dump(meta, open(D/'pinned.json', 'w'), indent=1); print(len(tiles), sheet.size)
