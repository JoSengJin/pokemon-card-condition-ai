"""Heuristic card-foreground mask for Pokemon card backs: convex hull of the largest blue component (no labels, no model)."""
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageOps

LONG_SIDE = 320
HSV_RANGE = dict(h=(134, 184), s_min=77, v_min=30)


def small_hsv(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
    scale = LONG_SIDE / max(im.size)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BILINEAR)
    return im, np.asarray(im.convert('HSV'))


def blue_pixels(hsv, window):
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    mask = (h >= HSV_RANGE['h'][0]) & (h <= HSV_RANGE['h'][1]) & (s >= HSV_RANGE['s_min']) & (v >= HSV_RANGE['v_min'])
    limit = np.zeros_like(mask)
    limit[window[1]:window[3], window[0]:window[2]] = True
    return mask & limit


def largest_component(mask):
    seen = np.zeros_like(mask); best = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        comp, queue = [], deque([(y, x)]); seen[y, x] = True
        while queue:
            cy, cx = queue.popleft(); comp.append((cx, cy))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; queue.append((ny, nx))
        best = max(best, comp, key=len)
    return best


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]
    return half(pts) + half(pts[::-1])


def card_mask(path, card_box, expand=0.10):
    """Return (thumbnail, boolean mask at thumbnail size, hull polygon in normalized photo coordinates)."""
    im, hsv = small_hsv(path)
    h, w = hsv.shape[:2]
    bw, bh = card_box[2] - card_box[0], card_box[3] - card_box[1]
    window = [max(0, int((card_box[0] - expand * bw) * w)), max(0, int((card_box[1] - expand * bh) * h)),
              min(w, int((card_box[2] + expand * bw) * w) + 1), min(h, int((card_box[3] + expand * bh) * h) + 1)]
    hull = convex_hull(largest_component(blue_pixels(hsv, window)))
    canvas = Image.new('L', (w, h), 0)
    if len(hull) >= 3:
        ImageDraw.Draw(canvas).polygon(hull, fill=255)
    return im, np.asarray(canvas) > 0, [(x / w, y / h) for x, y in hull]
