"""Synthetic checks for the corner template alignment diagnostic (no photos, no labels)."""
import importlib.util, itertools, math, unittest
from pathlib import Path
import numpy as np
from PIL import Image

PATH = Path(__file__).parents[1]/'tools/diagnostics/corner-template-align-20261124/align.py'
spec = importlib.util.spec_from_file_location('corner_template_align', PATH)
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
TIP = 88.8   # tip of a 30 px radius corner whose square corner sits at 80 on the canvas
CENTER = np.array([TIP + 50, TIP + 50])


def canvas(seed):
    """(300x300 canvas, its 120 px reference window): 10 px/mm: gray desk, rounded blue border, inner pattern that depends on the seed."""
    y, x = np.mgrid[:300, :300] + .5
    rng = np.random.default_rng(seed)
    waves = sum(np.sin(x*rng.uniform(-.25, .25) + y*rng.uniform(-.25, .25) + rng.uniform(0, 6)) for _ in range(6))
    img = np.full((300, 300, 3), 128.)
    d = np.where((x < 110) & (y < 110), 30 - np.hypot(x - 110, y - 110), np.minimum(x, y) - 80)
    img[d >= 0] = (30, 50, 160)
    inner = d >= 35
    img[inner] = (np.array([60, 90, 200]) + waves[..., None]*12)[inner]
    img = img.clip(0, 255).astype(np.uint8)
    return Image.fromarray(img), img[79:199, 79:199].astype(float)  # tip at about (10, 10)


def distorted(im, t, deg, k):
    """Photo point = 150 + k R(deg) (p - 150) + t, written independently of align.warp."""
    c, s = math.cos(math.radians(deg))/k, math.sin(math.radians(deg))/k
    ox, oy = 150 + t[0], 150 + t[1]
    return im.transform(im.size, Image.AFFINE, (c, s, 150 - c*ox - s*oy, -s, c, 150 + s*ox - c*oy), Image.BICUBIC, fillcolor=(128, 128, 128))


class Align(unittest.TestCase):
    def test_recovers_known_transform(self):
        im, ref = canvas(1)
        info = A.reference_info(ref)
        o = np.array([x + 1j*y for x in (-40, 0, 50) for y in (-40, 0, 50)])   # window points around its centre
        errs = []
        for t, deg, k in itertools.product([(-3, 3), (3, 0)], [-2, 0, 2], [.97, 1, 1.03]):
            got = A.align(distorted(im, t, deg, k), CENTER, ref, info['card'])
            want = 150 + 150j + complex(*t) + k*np.exp(1j*math.radians(deg))*(o + 139 + 139j - 150 - 150j)
            found = complex(*got['center']) + o*np.exp(1j*math.radians(got['deg']))/got['scale']
            errs.append(float(np.abs(found - want).mean()))
        self.assertLessEqual(float(np.median(errs)), .5, errs)

    def test_rotated_card_matches_diagonal_reference(self):
        refs = {'upper_left': canvas(1)[1], 'lower_right': canvas(2)[1]}
        infos = {a: A.reference_info(r) for a, r in refs.items()}
        for seed, want in ((1, 'upper_left'), (2, 'lower_right')):
            got = A.best_reference(distorted(canvas(seed)[0], (2, -1), 1, 1.01), (TIP, TIP), 'upper_left', refs, infos)
            self.assertEqual(got['ref'], want)

    def test_block_residual_reports_known_shift(self):
        im, ref = canvas(1)
        info = A.reference_info(ref)
        _, gray = A.warp(im, np.array([139. + 3, 139.]), 0, 1, A.SIZE + 2*A.REACH)  # 3 px misplaced on purpose
        info['blocks'] = [(1, 1), (1, 2), (2, 1), (2, 2)]
        for r in A.block_residuals(gray, ref, info):
            self.assertAlmostEqual(r, 3, delta=.5)

    def test_white_patch_raises_tip_residual(self):
        im, ref = canvas(1)
        info = A.reference_info(ref)
        clean = ref*.8 + 10  # exposure change is not a defect
        worn = clean.copy()
        worn[10:18, 10:18] = 250
        self.assertLess(A.tip_residual(clean, ref, info)[0], 1.5)
        self.assertGreater(A.tip_residual(worn, ref, info)[0], 8)

    def test_bright_background_still_prepares(self):
        a = np.asarray(canvas(1)[0]).copy()
        a[(a == 128).all(-1)] = 250
        status, _, tip = A.prepare_image(Image.fromarray(a), 10.0)
        self.assertEqual(status, 'ok')
        self.assertLess(abs(np.array(tip) - TIP).max(), 2)
        self.assertEqual(A.prepare_image(Image.fromarray(a[85:, 85:]), 10.0)[0], 'corner_cut')


if __name__ == '__main__':
    unittest.main()
