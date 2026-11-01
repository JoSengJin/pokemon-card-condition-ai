import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from card_condition.back_edge_triage import EDGE_AREAS, BackEdgeTriage, band, load_head

FORBIDDEN = ('결함입니다', '정상입니다', 'defect_verdict')


class FakeBody:
    def forward_features(self, tensor):
        generator = torch.Generator().manual_seed(int(tensor.abs().sum().item() * 1000) % 100000)
        return {'x_norm_patchtokens': torch.randn(1, 1024, 384, generator=generator)}


def make_head(folder, low=.31, high=.54):
    path = Path(folder)/'head.pt'
    torch.save(dict(coef=torch.randn(384) * .05, bias=torch.tensor(0.), band_low=low, band_high=high), path)
    return path


class BackEdgeTriageTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.image = Path(self.folder.name)/'back.png'
        Image.new('RGB', (300, 400), (90, 60, 160)).save(self.image)
        self.triage = BackEdgeTriage(make_head(self.folder.name), FakeBody())
        self.request = dict(id='x', side='back', image=str(self.image), box=[.05, .05, .95, .95], box_reviewed=True)

    def tearDown(self):
        self.folder.cleanup()

    def test_ranks_eight_edge_zones_without_verdict_words(self):
        result = self.triage.analyze(self.request)
        self.assertEqual('ranked', result['status'])
        self.assertEqual(sorted(EDGE_AREAS), sorted(z['area'] for z in result['zones']))
        scores = [z['score'] for z in result['zones']]
        self.assertEqual(sorted(scores, reverse=True), scores)
        self.assertEqual(list(range(1, 9)), [z['rank'] for z in result['zones']])
        self.assertNotIn('center', [z['area'] for z in result['zones']])
        self.assertTrue(all(w not in str(result) for w in FORBIDDEN))
        self.assertIn('판정이 아닙니다', result['notice'])

    def test_holds_without_confirmed_box_or_back_side(self):
        for change in (dict(box_reviewed=False), dict(box_reviewed=None), dict(side='front')):
            result = self.triage.analyze(dict(self.request, **change))
            self.assertEqual('held', result['status'])
            self.assertNotIn('zones', result)

    def test_holds_for_bad_input_and_does_not_mutate_request(self):
        for change in (dict(image='/no/such/file.png'), dict(box=[.9, .9, .1, .1]), dict(box='bad')):
            self.assertEqual('held', self.triage.analyze(dict(self.request, **change))['status'])
        snapshot = dict(self.request)
        self.triage.analyze(self.request)
        self.assertEqual(snapshot, self.request)


if __name__ == '__main__':
    unittest.main()
