"""v2 card-foreground mask: nearest-centroid background/foreground colours (box outside vs box core), majority filter, hull."""
import numpy as np
import torch
from PIL import Image, ImageOps
from mask import convex_hull, largest_component

LONG_SIDE, K, SEED = 320, 4, 20261111


def load_small(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
    scale = LONG_SIDE / max(im.size)
    return im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BILINEAR)


def centroids(points):
    rng = np.random.default_rng(SEED)
    pts = points[rng.choice(len(points), min(len(points), 4000), replace=False)].astype(float)
    cen = pts[rng.choice(len(pts), K, replace=False)]
    for _ in range(12):
        label = ((pts[:, None] - cen[None]) ** 2).sum(2).argmin(1)
        cen = np.array([pts[label == k].mean(0) if (label == k).any() else cen[k] for k in range(K)])
    return cen


def seeds(shape, box):
    h, w = shape; yy, xx = np.mgrid[0:h, 0:w]; x, y = xx / w, yy / h
    bw, bh = box[2] - box[0], box[3] - box[1]
    core = (x > box[0] + .25 * bw) & (x < box[2] - .25 * bw) & (y > box[1] + .25 * bh) & (y < box[3] - .25 * bh)
    outside = (x < box[0] - .03) | (x > box[2] + .03) | (y < box[1] - .03) | (y > box[3] + .03)
    if outside.sum() < 300:  # box covers almost the whole photo: fall back to the outer 2% ring
        outside = (x < .02) | (x > .98) | (y < .02) | (y > .98)
    return core, outside


def foreground(rgb, box):
    core, outside = seeds(rgb.shape[:2], box)
    fg, bg = centroids(rgb[core]), centroids(rgb[outside])
    pix = rgb.reshape(-1, 3).astype(float)
    dist = lambda c: ((pix[:, None] - c[None]) ** 2).sum(2).min(1)
    mask = torch.tensor((dist(fg) < dist(bg)).reshape(rgb.shape[:2]), dtype=torch.float32)[None, None]
    return (torch.nn.functional.avg_pool2d(mask, 5, 1, 2)[0, 0] > .5).numpy()


def card_mask2(path, box):
    """Return (thumbnail, mask, hull in normalized coords, bad flag)."""
    im = load_small(path); rgb = np.asarray(im); h, w = rgb.shape[:2]
    comp = largest_component(foreground(rgb, box)); hull = convex_hull(comp)
    canvas = Image.new('L', (w, h), 0)
    if len(hull) >= 3:
        from PIL import ImageDraw
        ImageDraw.Draw(canvas).polygon(hull, fill=255)
    norm = [(x / w, y / h) for x, y in hull]
    area = abs(sum(norm[i][0] * norm[(i + 1) % len(norm)][1] - norm[(i + 1) % len(norm)][0] * norm[i][1] for i in range(len(norm)))) / 2 if len(norm) >= 3 else 0
    mask = np.asarray(canvas) > 0; cx, cy = int((box[0] + box[2]) / 2 * w), int((box[1] + box[3]) / 2 * h)
    ratio = area / ((box[2] - box[0]) * (box[3] - box[1]))
    return im, mask, norm, (ratio < .5 or ratio > 1.05 or not mask[min(h - 1, cy), min(w - 1, cx)])
