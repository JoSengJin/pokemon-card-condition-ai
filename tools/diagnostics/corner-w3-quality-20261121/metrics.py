"""W3 step 1 (read-only): per-zone automatic image-quality metrics for the 946 corner zones: photo width px, crop width px, Laplacian variance of the grayscale crop, saturated-bright pixel fraction."""
import json
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def crop_metrics(img, box):
    w, h = img.size
    x0, y0, x1, y1 = box
    crop = img.convert('RGB').crop((int(x0*w), int(y0*h), int(x1*w), int(y1*h)))
    a = np.asarray(crop, dtype=np.float64)
    g = a.mean(2)
    lap = g[1:-1, 1:-1]*4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return dict(photo_w=w, crop_w=crop.size[0], crop_h=crop.size[1], lap_var=float(lap.var()), sat_frac=float((a.min(2) >= 250).mean()))


def main(rows_path, out_path):
    rows = json.load(open(rows_path))
    cache, out = {}, {}
    for r in rows:
        if r['image'] not in cache:
            cache.clear()
            cache[r['image']] = Image.open(r['image'])
        out[r['id']] = crop_metrics(cache[r['image']], r['box'])
    json.dump(out, open(out_path, 'w'))
    print(len(out))


if __name__ == '__main__':
    main(*sys.argv[1:3])
