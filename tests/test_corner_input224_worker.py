import importlib.util
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tools/experiments/corner-input224-cv-20261120/worker.py'


def load():
    spec = importlib.util.spec_from_file_location('corner224', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBody:
    """Returns finite patch tokens whose count follows the input size (224 -> 16x16 patches)."""

    def forward_features(self, tensor):
        side = tensor.shape[-1] // 14
        return {'x_norm_patchtokens': torch.ones(1, side * side, 384)}


def row(i, group, target, path, box=(.0, .0, .5, .5)):
    return dict(id=f'{group}/{i}', group=group, target=target, image=str(path), box=list(box), area='upper_left')


class Corner224Test(unittest.TestCase):
    def test_features_are_224_grid_and_mask_marks_resize_padding(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'a.png'
            Image.new('RGB', (600, 400), (90, 90, 90)).save(path)
            rows = [row(0, 'g', 0, path, (0, 0, 1, .5)), row(1, 'g', 1, path, (0, 0, .5, 1))]
            x, m = load().features224(FakeBody(), rows, 'cpu')
        self.assertEqual((2, 256, 384), tuple(x.shape))
        self.assertEqual((2, 256), tuple(m.shape))
        self.assertEqual(torch.bool, m.dtype)
        self.assertTrue(torch.isfinite(x).all())
        self.assertTrue(m.any(1).all())
        self.assertFalse(m.all(1).all(), 'a non-square crop must leave padded patches outside the mask')

    def test_wrong_token_shape_is_rejected(self):
        class Bad(FakeBody):
            def forward_features(self, tensor):
                return {'x_norm_patchtokens': torch.ones(1, 1024, 384)}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'a.png'
            Image.new('RGB', (300, 300)).save(path)
            with self.assertRaises(ValueError):
                load().features224(Bad(), [row(0, 'g', 0, path)], 'cpu')

    def test_events_count_photos_not_zones(self):
        rows = [row(i, 'pos1', t, 'p') for i, t in enumerate([1, 1, 0, 0])]
        rows += [row(i, 'pos2', t, 'p') for i, t in enumerate([1, 0, 0, 0])]
        rows += [row(i, 'neg1', 0, 'p') for i in range(4)] + [row(i, 'neg2', 0, 'p') for i in range(4)]
        scores = [.2, .2, .1, .9,   .7, .1, .1, .1,   .6, .6, .1, .1,   .3, .3, .3, .3]
        ev = load().l_events(rows, scores)
        # pos1: two defect zones below .281 -> one missed photo; pos2: defect .7 -> not missed
        self.assertEqual(dict(miss=1, positives=2, false_alarm=1, normals=2), ev)

    def test_events_use_frozen_thresholds(self):
        w = load()
        self.assertEqual((.281, .509, 224, 16), (w.LOW, w.HIGH, w.SIZE, w.GRID))


if __name__ == '__main__':
    unittest.main()
