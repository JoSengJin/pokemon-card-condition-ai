import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from card_condition.back_edge_triage import BackEdgeTriage, band, load_head
from tests.test_back_edge_triage import FakeBody, make_head


class BackEdgeTriageGuardTest(unittest.TestCase):
    def test_band_boundaries_head_validation_and_determinism(self):
        self.assertEqual(['low', 'mid', 'high'], [band(.309, .31, .54), band(.31, .31, .54), band(.54, .31, .54)])
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/'bad.pt'
            torch.save(dict(coef=torch.zeros(10), bias=torch.tensor(0.), band_low=.3, band_high=.5), bad)
            with self.assertRaises(ValueError):
                load_head(bad)
            image = Path(folder)/'back.png'
            Image.new('RGB', (300, 400), (90, 60, 160)).save(image)
            triage = BackEdgeTriage(make_head(folder), FakeBody())
            request = dict(id='x', side='back', image=str(image), box=[.05, .05, .95, .95], box_reviewed=True)
            self.assertEqual(64, len(load_head(make_head(folder))['sha256']))
            self.assertEqual(triage.analyze(request), triage.analyze(request))

    def test_non_finite_scores_hold(self):
        class Bad:
            def forward_features(self, tensor):
                return {'x_norm_patchtokens': torch.full((1, 1024, 384), float('nan'))}
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder)/'back.png'
            Image.new('RGB', (300, 400), (90, 60, 160)).save(image)
            result = BackEdgeTriage(make_head(folder), Bad()).analyze(dict(id='x', side='back', image=str(image), box=[.05, .05, .95, .95], box_reviewed=True))
            self.assertEqual('held', result['status'])


if __name__ == '__main__':
    unittest.main()
