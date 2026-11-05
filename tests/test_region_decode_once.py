from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import torch
from card_condition.region_model import RegionAnalyzer
from card_condition.edge_views import region_features
from card_condition.regions import GLARE_AREAS,REGION_LABELS


class RegionDecodeOnceTests(unittest.TestCase):
    def test_same_outputs_and_only_context_shares_decode(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'photo.png';Image.effect_noise((137,213),31).convert('RGB').save(image)
            analyzer=RegionAnalyzer.__new__(RegionAnalyzer);analyzer.device=torch.device('cpu')
            analyzer.backbone=torch.nn.Conv2d(3,4,3,stride=4,padding=1).eval()
            analyzer.meta=dict(supported=list(REGION_LABELS),architecture='fixture');analyzer.model_sha256='fixed'
            for policy in (False,True,'tiles','tiles-max'):
                analyzer.policy=policy;analyzer.head=torch.nn.Linear(8 if policy else 4,3).eval()
                for size in (224,448):
                    analyzer.image_size=size
                    for batch in (False,True):
                        with self.subTest(policy=policy,size=size,batch=batch):
                            with patch('PIL.Image.open',wraps=Image.open) as opened:
                                old=[analyzer.analyze(str(image),[.03,.07,.98,.99],area,batch_views=batch) for area in GLARE_AREAS]
                                self.assertEqual(9,opened.call_count)
                            with patch('PIL.Image.open',wraps=Image.open) as opened:
                                new=analyzer.analyze_regions(str(image),[.03,.07,.98,.99],list(GLARE_AREAS),batch_views=batch)
                                self.assertEqual(9 if policy else 1,opened.call_count)
                            for a,b in zip(old,new):
                                a.pop('elapsed_seconds');b.pop('elapsed_seconds');self.assertEqual(a,b)

    def test_no_open_for_empty_or_invalid_and_no_cross_request_cache(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'photo.png';Image.new('RGB',(41,57),'white').save(image)
            analyzer=RegionAnalyzer.__new__(RegionAnalyzer);analyzer.device=torch.device('cpu');analyzer.policy=False
            analyzer.image_size=224;analyzer.backbone=torch.nn.Identity().eval();analyzer.head=torch.nn.Linear(3,3).eval()
            analyzer.meta=dict(supported=list(REGION_LABELS),architecture='fixture');analyzer.model_sha256='fixed'
            with patch('PIL.Image.open',wraps=Image.open) as opened:
                self.assertEqual([],analyzer.analyze_regions(str(image),[0,0,1,1],[]));self.assertEqual(0,opened.call_count)
                before=analyzer.analyze_regions(str(image),[0,0,1,1],['center'])
                Image.new('RGB',(41,57),'black').save(image)
                after=analyzer.analyze_regions(str(image),[0,0,1,1],['center']);self.assertEqual(2,opened.call_count)
            self.assertNotEqual(before[0]['probabilities'],after[0]['probabilities'])
            for areas,batch in ((['center','center'],False),('center',False),(['bad'],False),([],1)):
                with self.assertRaises(ValueError):analyzer.analyze_regions(str(image),[0,0,1,1],areas,batch_views=batch)
            with torch.inference_mode(),self.assertRaisesRegex(ValueError,'one image'):
                list(region_features(analyzer.backbone,[dict(image='a',card_box=[0,0,1,1]),dict(image='b',card_box=[0,0,1,1])],'cpu'))
