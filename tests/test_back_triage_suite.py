import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from card_condition.back_obs_limit import BackObservationLimit, load_head as load_obs_head
from card_condition.back_triage_suite import BackTriageSuite
from card_condition.back_zone_triage import BackZoneTriage
from tests.test_back_edge_triage import FakeBody, make_head

FORBIDDEN = ('결함입니다', '정상입니다', 'defect_verdict', 'limited_verdict')


def obs_head(folder):
    path = Path(folder)/'obs.pt'
    torch.save(dict(mean=torch.zeros(384), std=torch.ones(384), coef=torch.randn(384)*.05, bias=torch.tensor(0.)), path)
    return path


class BackTriageSuiteTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.image = Path(self.folder.name)/'back.png'
        Image.new('RGB', (300, 400), (90, 60, 160)).save(self.image)
        heads = dict(edge=make_head(self.folder.name), corner=make_head(self.folder.name), surface=make_head(self.folder.name), observation_limit=obs_head(self.folder.name))
        self.suite = BackTriageSuite(heads, FakeBody())
        self.request = dict(id='x', side='back', image=str(self.image), box=[.05, .05, .95, .95], box_reviewed=True)

    def tearDown(self):
        self.folder.cleanup()

    def test_back_returns_four_parts_with_zone_counts_and_no_verdict(self):
        out = self.suite.analyze(self.request)
        r = out['results']
        self.assertEqual((8, 4, 9), tuple(len(r[k]['zones']) for k in ('edge', 'corner', 'surface')))
        self.assertEqual('scored', r['observation_limit']['status'])
        self.assertTrue(0 <= r['observation_limit']['score'] <= 1)
        self.assertFalse(out['complete'])
        self.assertEqual({'centering', 'front_face'}, set(out['unsupported']))
        self.assertTrue(all(w not in str(out) for w in FORBIDDEN))

    def test_front_or_unconfirmed_box_is_held_everywhere(self):
        for change in (dict(side='front'), dict(box_reviewed=False)):
            out = self.suite.analyze(dict(self.request, **change))
            self.assertEqual({'held'}, {p['status'] for p in out['results'].values()})

    def test_bad_input_holds_and_request_unchanged(self):
        snapshot = dict(self.request)
        out = self.suite.analyze(dict(self.request, image='/no/such.png'))
        self.assertEqual({'held'}, {p['status'] for p in out['results'].values()})
        self.suite.analyze(self.request)
        self.assertEqual(snapshot, self.request)

    def test_head_validation_and_determinism(self):
        bad = Path(self.folder.name)/'bad.pt'
        torch.save(dict(mean=torch.zeros(5), std=torch.ones(5), coef=torch.zeros(5), bias=torch.tensor(0.)), bad)
        with self.assertRaises(ValueError):
            load_obs_head(bad)
        self.assertEqual(self.suite.analyze(self.request), self.suite.analyze(self.request))
        with self.assertRaises(KeyError):
            BackZoneTriage('centering', make_head(self.folder.name), FakeBody())
