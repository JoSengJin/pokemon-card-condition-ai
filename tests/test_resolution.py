import unittest
import tempfile
from pathlib import Path
import torch
from test_pipeline import fixture
from card_condition.data import image_tensor
from card_condition.model import train, Analyzer

class ResolutionTest(unittest.TestCase):
    def test_resolution_roundtrip_and_legacy_default(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); manifest,_=fixture(root)
            self.assertEqual((3,448,448),tuple(image_tensor(None,448).shape))
            with self.assertRaises(ValueError): image_tensor(None,123)
            path=root/'large.pt'
            train(manifest,path,epochs=1,device='cpu',pretrained=False,image_size=448)
            analyzer=Analyzer(path,'cpu')
            self.assertEqual(448,analyzer.image_size)
            self.assertTrue(analyzer.analyze(root/'4-front.png')['requires_gemini'])
            meta=torch.load(path,weights_only=True);del meta['image_size'];torch.save(meta,path)
            self.assertEqual(224,Analyzer(path,'cpu').image_size)
            meta['image_size']=123;torch.save(meta,path)
            with self.assertRaisesRegex(ValueError,'image_size'): Analyzer(path,'cpu')
