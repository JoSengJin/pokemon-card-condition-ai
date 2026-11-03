"""Diagnosis only (no ./experiment record, no model, holdout untouched): draw human 4-tap lines on train fronts whose tap asymmetry disagrees with the label."""
import json
from PIL import Image, ImageDraw, ImageOps

A = 'artifacts/c4-expansion-20261103/'
OUT = 'artifacts/c4-label-criterion-diagnosis-20261103/'
pool = {r['id']: r for r in json.load(open(A + 'pool.json'))}
tr = [x for x in json.load(open(A + 'train4-widths.json')) if x['box_ok']]
assert all(pool[x['id']]['role'] != 'holdout' for x in tr)
pick = [x for x in tr if (x['label'] == '정상' and x['tb'] >= .15) or (x['label'] == '결함' and x['tb'] < .04)]
tiles = []
for x in pick:
    p = pool[x['id']]
    im = ImageOps.exif_transpose(Image.open(p['image'])).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    for k, c in (('outer_top', 'red'), ('outer_bottom', 'red'), ('inner_top', 'blue'), ('inner_bottom', 'blue')):
        d.line([0, x[k] * h, w, x[k] * h], fill=c, width=max(2, h // 400))
    x0, _, x1, _ = p['box']
    im = im.crop((max(0, (x0 - .05) * w), max(0, (x['outer_top'] - .04) * h), min(w, (x1 + .05) * w), min(h, (x['outer_bottom'] + .04) * h)))
    im.thumbnail((420, 600))
    t = Image.new('RGB', (430, 640), 'white'); t.paste(im, (5, 30))
    ImageDraw.Draw(t).text((5, 5), f"{x['label']=='결함' and 'DEFECT' or 'NORMAL'} tb={x['tb']:.2f} {x['id'][-6:]}", fill='black')
    tiles.append(t)
cols = 4
sheet = Image.new('RGB', (430 * cols, 640 * ((len(tiles) + cols - 1) // cols)), 'white')
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 430, (i // cols) * 640))
sheet.save(OUT + 'discordant.jpg', quality=82)
print(len(pick), [(x['label'], round(x['tb'], 2), x['id'][-6:]) for x in pick])
