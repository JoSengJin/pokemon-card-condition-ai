"""Back-corner alignment to an area-specific reference. Never reads labels or model scores.

Rules and constants: docs/collaboration/reports/corner-template-align-20261124.md (fixed before results).
Coordinates are continuous (pixel i spans i..i+1), 10 px/mm, corner toward the top-left.
"""
import math, sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]/'corner-size-threshold-20261123'))
import measure as M

PPM, SIZE, TIP_AT, REACH = 10.0, 120, 10.0, 6   # 12x12 mm window, tip 1 mm inside it, block search +-6 px
RADIUS = 30.0                                   # 3 mm card corner radius (measure.py)
MAX_MOVE = 20.0                                 # fine alignment may move at most 2 mm from the blue-border tip
DIAGONAL = {'upper_left': 'lower_right', 'lower_right': 'upper_left', 'upper_right': 'lower_left', 'lower_left': 'upper_right'}
LEVELS = [([-3, -2, -1, 0, 1, 2, 3], [-.05, -.025, 0, .025, .05])] + [([-d, 0, d], [-s, 0, s]) for d, s in ((.5, .0125), (.25, .006), (.125, .003))]
MIN_BLOCK_ENERGY = 0.5  # set from the reference images only, before stage A


def prepare_image(im, ppm):
    """(status, image at 10 px/mm, tip). measure_array finds the tip; its bright-background refusal is off here."""
    with patch.object(M, 'BG_V95_MAX', 9.0):
        out, _ = M.measure_array(np.asarray(im), ppm)
    if out['status'] != 'ok':
        return out['status'], None, None
    k = PPM/ppm
    small = im.resize((max(1, round(im.width*k)), max(1, round(im.height*k))), Image.LANCZOS)
    tip = ((np.array(out['apex']) + .5)*np.array(small.size)/np.array(im.size)).tolist()
    if min(small.width - tip[0], small.height - tip[1]) < SIZE - TIP_AT + REACH:
        return 'window_outside', None, None
    return 'ok', small, tip


def warp(im, center, deg, scale, size):
    """Window of `size` px around `center`: (RGB float array, gray float array)."""
    c, s = math.cos(math.radians(deg))/scale, math.sin(math.radians(deg))/scale
    h = size/2
    rgb = np.asarray(im.transform((size, size), Image.AFFINE, (c, -s, center[0] - c*h + s*h, s, c, center[1] - s*h - c*h), Image.BICUBIC), float)
    return rgb, rgb @ (.299, .587, .114)


def align(im, center0, ref, card):
    """Phase correlation for shift, grid search for rotation/scale; best card-area NCC, or None."""
    g_ref = ref @ (.299, .587, .114)
    f = np.fft.fftfreq(SIZE)
    low = np.exp(-(f[:, None]**2 + f[None]**2)/(2*.15**2))   # band limit: the peak becomes a ~1 px Gaussian
    soft = np.hanning(SIZE + 2)[1:-1]**.5
    weight = soft[:, None]*soft[None]*card
    F_ref = np.conj(np.fft.fft2((g_ref - g_ref[card].mean())*weight))
    best, center0 = None, np.array(center0, float)
    for degs, scales in LEVELS:
        base = best or dict(center=center0, deg=0.0, scale=1.0)
        if best is None and degs != LEVELS[0][0]:
            return None
        for deg in {min(3, max(-3, base['deg'] + d)) for d in degs}:
            for scale in {min(1.05, max(.95, base['scale'] + s)) for s in scales}:
                center = np.array(base['center'])
                for _ in range(2):
                    _, g = warp(im, center, deg, scale, SIZE)
                    cross = np.fft.fft2((g - g[card].mean())*weight)*F_ref
                    peak = np.real(np.fft.ifft2(cross/(np.abs(cross) + 1e-6)*low))
                    py, px = np.unravel_index(peak.argmax(), peak.shape)
                    d = []
                    for a, b, c in ((peak[py, px - 1], peak[py, px], peak[py, (px + 1) % SIZE]), (peak[py - 1, px], peak[py, px], peak[(py + 1) % SIZE, px])):
                        a, b, c = np.log(np.maximum((a, b, c), 1e-9))
                        d.append(float(np.clip((a - c)/(2*(a - 2*b + c) - 1e-9), -.5, .5)))
                    shift = (np.array([px + d[0], py + d[1]]) + SIZE/2) % SIZE - SIZE/2
                    r = math.radians(deg)
                    center = center + np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]]) @ shift/scale
                if np.linalg.norm(center - center0) > MAX_MOVE:
                    continue
                _, g = warp(im, center, deg, scale, SIZE)
                ncc = float(np.corrcoef(g[card], g_ref[card])[0, 1])
                if best is None or ncc > best['ncc']:
                    best = dict(center=center.tolist(), deg=deg, scale=scale, ncc=ncc)
    return best


def best_reference(im, tip, area, refs, infos):
    """Try the zone's own reference and the diagonal one (card photographed upside down); higher NCC wins."""
    center0 = np.array(tip) + SIZE/2 - TIP_AT
    tried = {a: align(im, center0, refs[a], infos[a]['card']) for a in (area, DIAGONAL[area])}
    found = {a: t for a, t in tried.items() if t}
    if not found:
        return None
    ref = max(found, key=lambda a: found[a]['ncc'])
    return dict(found[ref], ref=ref, ncc_by_ref={a: t['ncc'] for a, t in found.items()})


def reference_info(ref):
    """Card area (round corner drawn from card geometry), tip, and per-block weakest-direction gradient energy."""
    rgb = np.asarray(ref).clip(0, 255).astype(np.uint8)
    yy, xx = np.mgrid[:SIZE, :SIZE] + .5
    edge, far = TIP_AT - RADIUS*(1 - .5**.5), TIP_AT + RADIUS*.5**.5   # card edge line, arc centre
    card = (xx >= edge) & (yy >= edge) & ((xx >= far) | (yy >= far) | (np.hypot(xx - far, yy - far) <= RADIUS))
    gy, gx = np.gradient(rgb @ (.299, .587, .114))
    energy, n = {}, SIZE//3
    for by in range(3):
        for bx in range(3):
            w = (slice(by*n, (by + 1)*n), slice(bx*n, (bx + 1)*n))
            inside = card[w] & M.grow(card, 2, shrink=True)[w]   # the card outline itself is not a pattern
            x, y = gx[w][inside], gy[w][inside]
            # weakest direction: a straight edge alone cannot fix both axes
            energy[by, bx] = float(np.linalg.eigvalsh(np.cov(np.stack([x, y]), bias=True)
                                   + np.outer((x.mean(), y.mean()), (x.mean(), y.mean())))[0]) if inside.mean() >= .5 else 0.0
    return dict(card=card, tip=[TIP_AT, TIP_AT], energy=energy,
                blocks=[k for k, e in energy.items() if e > MIN_BLOCK_ENERGY])


def block_residuals(gray, ref, info):
    """Remaining shift (px) of each usable block. gray: aligned window with a REACH px margin on every side."""
    g_ref, out, n = ref @ (.299, .587, .114), [], SIZE//3
    for by, bx in info['blocks']:
        w = (slice(by*n, (by + 1)*n), slice(bx*n, (bx + 1)*n))
        m = info['card'][w]
        t = g_ref[w][m] - g_ref[w][m].mean()
        area = gray[by*n:(by + 1)*n + 2*REACH, bx*n:(bx + 1)*n + 2*REACH]
        c = np.lib.stride_tricks.sliding_window_view(area, (n, n))[:, :, m]
        c = c - c.mean(-1, keepdims=True)
        score = (c @ t)/(np.sqrt((c**2).sum(-1)*(t**2).sum()) + 1e-9)
        py, px = np.unravel_index(score.argmax(), score.shape)
        d = np.array([px - REACH, py - REACH], float)
        for k, v in enumerate((score[py, px - 1:px + 2] if 0 < px < 2*REACH else [], score[py - 1:py + 2, px] if 0 < py < 2*REACH else [])):
            if len(v):
                d[k] += float((v[0] - v[2])/(2*(v[0] - 2*v[1] + v[2]) - 1e-9))
        out.append(float(np.linalg.norm(d)))
    return out


def tip_residual(rgb, ref, info):
    """(mean |matched - reference| within ARC_MM of the tip, residual map, matched crop)."""
    card, matched = info['card'], np.empty_like(rgb, float)
    for k in range(3):
        a, b = rgb[..., k][card], ref[..., k][card]   # mean/std match: least squares would shrink contrast when the match is poor
        matched[..., k] = (rgb[..., k] - a.mean())*b.std()/(a.std() + 1e-6) + b.mean()
    diff = np.abs(matched - ref).mean(-1)
    yy, xx = np.mgrid[:SIZE, :SIZE] + .5
    near = card & ((xx - info['tip'][0])**2 + (yy - info['tip'][1])**2 <= (M.ARC_MM*PPM)**2)
    return float(diff[near].mean()), diff, matched
