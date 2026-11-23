"""Corner whitening size from pixels only (Pillow/numpy). Never reads labels or model scores.

Per zone: px/mm from the card box (zone = 1/3 of the card box; card 63x88 mm), then the area of
white pixels within 1 mm of the blue border and 2.5 mm of the corner tip, reported as sqrt(area) in mm.
Not measured: non-blue borders, tip outside the crop, background too bright to tell from whitening.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

CARD_MM = (63.0, 88.0)
PAD = 0.25            # same padding as the review crop (tools/relabel_zone_pages.crop)
BLUE_H, BLUE_S, BLUE_V = (195.0, 265.0), 0.35, 0.08   # card-back border colour
BLUE_MIN_SHARE = 0.03  # less blue than this in the crop = not a blue-bordered back, not measured
ARC_MM, RIM_MM = 2.5, 1.0   # arc ends are 2.3 mm from the arc midpoint for a 3 mm corner radius
WHITE_S, WHITE_V = 0.30, 0.62
BG_V95_MAX = 0.55     # background beyond the tip brighter than this cannot be told from whitening
FLIP = {'upper_left': (False, False), 'upper_right': (True, False), 'lower_left': (False, True), 'lower_right': (True, True)}


def px_per_mm(box, w, h):
    l, t, r, b = box
    return (3*(r - l)*w/CARD_MM[0] + 3*(b - t)*h/CARD_MM[1])/2


def oriented_crop(z):
    """Padded zone crop turned so the card corner points to the top-left."""
    with Image.open(z['image']) as src:
        im = ImageOps.exif_transpose(src).convert('RGB')
    w, h = im.size
    l, t, r, b = z['box']
    mx, my = (r - l)*PAD, (b - t)*PAD
    out = im.crop([int(max(0, (l - mx)*w)), int(max(0, (t - my)*h)), int(min(w, (r + mx)*w)), int(min(h, (b + my)*h))])
    fx, fy = FLIP[z['area']]
    if fx: out = ImageOps.mirror(out)
    if fy: out = ImageOps.flip(out)
    return out, px_per_mm(z['box'], w, h)


def hsv(rgb):
    f = rgb.astype(np.float32)/255
    mx, mn = f.max(-1), f.min(-1)
    d = mx - mn
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    with np.errstate(divide='ignore', invalid='ignore'):
        h = np.where(mx == r, (g - b)/d % 6, np.where(mx == g, (b - r)/d + 2, (r - g)/d + 4))*60
        s = np.where(mx > 0, d/mx, 0)
    return np.nan_to_num(h), s, mx


def grow(mask, k, shrink=False):
    """Square dilation (or erosion) by k px; k passes of 3x3 equal one (2k+1) pass and are faster."""
    im, f = Image.fromarray((mask*255).astype(np.uint8)), (ImageFilter.MinFilter if shrink else ImageFilter.MaxFilter)(3)
    for _ in range(k):
        im = im.filter(f)
    return np.asarray(im) > 0


def measure_array(rgb, ppm):
    """rgb: HxWx3 uint8 with the corner toward (0,0). Returns (dict(status, size_mm, ...), white mask)."""
    h, w = rgb.shape[:2]
    hue, sat, val = hsv(rgb)
    out = dict(ppm=round(float(ppm), 2), size_mm=None, area_mm2=None)
    blue = (hue >= BLUE_H[0]) & (hue <= BLUE_H[1]) & (sat >= BLUE_S) & (val >= BLUE_V)
    blue = grow(grow(blue, 2, shrink=True), 2)  # drop speckles
    if blue.mean() < BLUE_MIN_SHARE:
        return dict(out, status='no_blue_border'), None
    ys, xs = np.nonzero(blue)
    s = xs + ys
    near = s <= s.min() + 2
    ax, ay = float(xs[near].mean()), float(ys[near].mean())
    yy, xx = np.mgrid[:h, :w]
    k = max(1, int(round(RIM_MM*ppm)))
    beyond = ~grow(blue, k) & (xx + yy < ax + ay)  # outward of the tip: background
    if ax < 2 or ay < 2 or beyond.sum() < 50:
        return dict(out, status='corner_cut'), None
    if np.percentile(val[beyond], 95) >= BG_V95_MAX:
        return dict(out, status='bg_bright'), None
    ring = grow(blue, k) & ((xx - ax)**2 + (yy - ay)**2 <= (ARC_MM*ppm)**2)
    white = ring & (sat <= WHITE_S) & (val >= WHITE_V)
    area = float(white.sum())/ppm**2
    return dict(out, status='ok', area_mm2=round(area, 4), size_mm=round(area**.5, 4), apex=[round(ax, 1), round(ay, 1)]), white


def measure(z):
    im, ppm = oriented_crop(z)
    return measure_array(np.asarray(im), ppm)[0]


def selfcheck():
    """Synthetic corner: blue card on black, a 12x12 px white patch at the tip, 10 px/mm -> 1.2 mm."""
    a = np.zeros((300, 300, 3), np.uint8)
    a[40:, 40:] = (30, 50, 160)
    a[40:52, 40:52] = (250, 250, 250)
    r, _ = measure_array(a, 10.0)
    assert r['status'] == 'ok' and abs(r['size_mm'] - 1.2) < .05, r
    a[40:52, 40:52] = (30, 50, 160)
    assert measure_array(a, 10.0)[0]['size_mm'] == 0, 'clean corner must measure 0'
    a[:] = 250
    a[40:, 40:] = (30, 50, 160)
    assert measure_array(a, 10.0)[0]['status'] == 'bg_bright'
    return 'measure selfcheck ok'


if __name__ == '__main__':
    print(selfcheck())
