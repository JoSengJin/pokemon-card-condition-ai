import importlib.util
import re
import unittest
from pathlib import Path

import torch

DIR = Path(__file__).resolve().parents[1] / 'tools/experiments/corner-canonical-orientation-20261124'
spec = importlib.util.spec_from_file_location('orient_transform', DIR / 'transform.py')
transform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transform)
AREAS = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
CORNERS = dict(upper_left=(0, 0), upper_right=(0, 5), lower_left=(5, 0), lower_right=(5, 5))


def zone(area):
    """6x6 zone with one marker pixel (value 9) on the corner the area names, plus a mask copy."""
    tensor = torch.zeros(3, 6, 6)
    y, x = CORNERS[area]
    tensor[:, y, x] = 9
    return tensor, tensor[0] == 9


def shift(tensor, dx, dy):
    moved = torch.zeros_like(tensor)
    moved[..., dy:, dx:] = tensor[..., :6-dy, :6-dx]
    return moved


class CanonicalOrientationTest(unittest.TestCase):
    def test_apex_marker_lands_upper_left_for_every_area(self):
        for area in AREAS:
            tensor, mask = zone(area)
            flipped, flipped_mask = transform.canonical(tensor, mask, area)
            self.assertTrue((flipped[:, 0, 0] == 9).all() and flipped.sum() == 27, area)
            self.assertTrue(flipped_mask[0, 0] and flipped_mask.sum() == 1, area)

    def test_asymmetric_pattern_matches_the_flip_for_its_area(self):
        tensor = torch.arange(36.).reshape(1, 6, 6).expand(3, 6, 6).clone()
        mask = torch.arange(36).reshape(6, 6) % 3 == 0
        expected = dict(upper_left=lambda a: a, upper_right=lambda a: a.flip(-1),
                        lower_left=lambda a: a.flip(-2), lower_right=lambda a: a.flip(-1).flip(-2))
        for area in AREAS:
            flipped, flipped_mask = transform.canonical(tensor, mask, area)
            self.assertTrue(torch.equal(flipped, expected[area](tensor)), area)
            self.assertTrue(torch.equal(flipped_mask, expected[area](mask)), area)

    def test_involution_and_inputs_untouched(self):
        tensor = torch.rand(3, 6, 6)
        mask = tensor[0] > .5
        before, before_mask = tensor.clone(), mask.clone()
        for area in AREAS:
            flipped, flipped_mask = transform.canonical(tensor, mask, area)
            self.assertTrue(torch.equal(flipped_mask, flipped[0] > .5), area)
            back, back_mask = transform.canonical(flipped, flipped_mask, area)
            flipped.zero_()
            flipped_mask.zero_()
            self.assertTrue(torch.equal(back, tensor) and torch.equal(back_mask, mask), area)
            self.assertTrue(torch.equal(tensor, before) and torch.equal(mask, before_mask), area)

    def test_unknown_area_raises(self):
        tensor, mask = zone('upper_left')
        for area in ('center', 'upper-left', '', None):
            with self.assertRaises(ValueError):
                transform.canonical(tensor, mask, area)

    def test_flip_then_shift_order_is_what_the_worker_uses(self):
        tensor, mask = zone('upper_right')
        flip_first = shift(transform.canonical(tensor, mask, 'upper_right')[0], 2, 1)
        shift_first = transform.canonical(shift(tensor, 2, 1), mask, 'upper_right')[0]
        self.assertFalse(torch.equal(flip_first, shift_first))
        self.assertTrue((flip_first[:, 1, 2] == 9).all())
        source = (DIR / 'worker.py').read_text()
        loop = re.search(r'for i, t, m in oriented_views\(rows, keep\):(.*?)values\[i\]', source, re.S).group(1)
        self.assertIn('grid.moved_input(t, m, dx, dy)', loop)
        self.assertIn('orient.canonical(t, mask, rows[i][\'area\'])', source)
        self.assertIn('extract_train(body, all_rows', source)
        self.assertNotIn('moved_input', source.split('def score_four_phases')[0])
