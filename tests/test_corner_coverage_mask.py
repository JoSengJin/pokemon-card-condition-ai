import importlib.util
from pathlib import Path
import unittest

import torch

PATH = Path(__file__).resolve().parents[1] / 'tools/experiments/corner-coverage-mask-20261124/transform.py'
spec = importlib.util.spec_from_file_location('coverage_transform', PATH)
transform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transform)


def control(real):
    return real.reshape(32, 14, 32, 14).any(3).any(1).flatten()


def patch_with(pixels):
    real = torch.zeros(448, 448, dtype=torch.bool)
    flat = torch.zeros(196, dtype=torch.bool)
    flat[:pixels] = True
    real[:14, :14] = flat.reshape(14, 14)
    return real


class CoverageMaskTest(unittest.TestCase):
    def test_full_image_matches_control(self):
        real = torch.ones(448, 448, dtype=torch.bool)
        self.assertTrue(torch.equal(transform.patch_valid(real), control(real)))
        self.assertEqual(int(transform.patch_valid(real).sum()), 1024)

    def test_boundary_at_97_98_196_pixels(self):
        for pixels in (97, 98, 196):
            real = patch_with(pixels)
            real[:14, 14:28] = True  # a second full patch exists, so no fallback
            valid = transform.patch_valid(real)
            self.assertEqual(bool(valid[0]), pixels >= 98)
            self.assertTrue(bool(valid[1]))
        lone = patch_with(97)  # no other qualifying patch -> control fallback keeps it
        self.assertTrue(torch.equal(transform.patch_valid(lone), control(lone)))
        self.assertEqual(int(transform.patch_valid(lone).sum()), 1)

    def test_all_padding_falls_back_to_control(self):
        real = torch.zeros(448, 448, dtype=torch.bool)
        self.assertEqual(int(transform.patch_valid(real).sum()), 0)
        thin = torch.zeros(448, 448, dtype=torch.bool)
        thin[:3, :] = True  # 42 px per patch in the top row, below half everywhere
        self.assertTrue(torch.equal(transform.patch_valid(thin), control(thin)))
        self.assertEqual(int(transform.patch_valid(thin).sum()), 32)

    def test_shifted_masks_follow_moved_input(self):
        real = torch.zeros(448, 448, dtype=torch.bool)
        real[7:, 7:] = True  # same placement as moved_input
        valid = transform.patch_valid(real).reshape(32, 32)
        self.assertFalse(bool(valid[0, 0]))  # 7x7 = 49 pixels
        self.assertTrue(bool(valid[0, 5]))  # 7x14 = 98 -> exactly half
        self.assertTrue(control(real).reshape(32, 32)[0, 0])
        self.assertEqual(int(valid.sum()), 1023)

    def test_padded_high_score_dropped_interior_max_kept(self):
        real = torch.zeros(448, 448, dtype=torch.bool)
        real[7:, 7:] = True
        logits = torch.zeros(1024)
        logits[0] = 9.  # corner patch: mostly padding
        logits[33 * 5] = 3.  # interior patch
        control_best = logits.masked_fill(~control(real), -torch.inf).amax()
        best = logits.masked_fill(~transform.patch_valid(real), -torch.inf).amax()
        self.assertEqual(float(control_best), 9.)
        self.assertEqual(float(best), 3.)


if __name__ == '__main__':
    unittest.main()
