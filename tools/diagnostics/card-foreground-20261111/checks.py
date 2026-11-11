"""Synthetic checks: blue-card-on-white mask, hull geometry, outside-rate rules, bootstrap sign."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from PIL import Image, ImageDraw
from mask import card_mask, convex_hull
from analysis import outside_rates, bootstrap

with tempfile.TemporaryDirectory() as t:
    p = Path(t) / 'a.png'; im = Image.new('RGB', (400, 600), (245, 245, 245)); ImageDraw.Draw(im).rectangle([100, 100, 300, 500], fill=(30, 50, 160)); im.save(p)
    _, m, hull = card_mask(p, [0.2, 0.15, 0.8, 0.85])
    h, w = m.shape; assert m[int(.5 * h), int(.5 * w)] and not m[int(.05 * h), int(.05 * w)] and not m[int(.95 * h), int(.95 * w)]
    assert 0.2 < m.mean() < 0.35
assert sorted(convex_hull([(0, 0), (4, 0), (4, 4), (0, 4), (2, 2)])) == [(0, 0), (0, 4), (4, 0), (4, 4)]
mm = np.zeros((100, 100), bool); mm[20:80, 20:80] = True
assert outside_rates(mm, [.4, .4, .5, .5]) == (0, 0) and outside_rates(mm, [.0, .0, .1, .1]) == (1, 1) and outside_rates(mm, [.65, .4, .85, .6])[0] == 0 and outside_rates(mm, [.75, .4, .95, .6])[0] == 1
rows = [dict(group=str(i), outcome='FP' if i % 2 else 'TN', center_out=1 if i % 2 else 0) for i in range(40)]
lo, hi = bootstrap(rows, draws=200); assert lo > 0.5 and hi <= 1.0
print('PASS: synthetic blue card mask/hull/outside-rate/bootstrap'); print(dict(real_photos=0, model_calls=0))
