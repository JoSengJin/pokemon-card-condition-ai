import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import torch
from torch import nn

from card_condition.observation_backbone import DINOV2_REVISION, dino_backbone
from card_condition.visibility_model import experiment, VisibilityAnalyzer, TARGET
import test_visibility_model


class FakeDino(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection=nn.Conv2d(3,384,1)

    def forward(self, image):
        return self.projection(image).mean((2,3))


class ObservationBackboneTest(unittest.TestCase):
    def test_pinned_frozen_descriptor_contract(self):
        with patch('card_condition.observation_backbone.torch.hub.load',side_effect=lambda *a,**k:FakeDino()) as loader:
            model,dimension=dino_backbone(True)
            self.assertEqual(384,dimension)
            self.assertEqual((1,384,1,1),tuple(model(torch.zeros(1,3,14,14)).shape))
            self.assertFalse(model.training)
            self.assertTrue(all(not p.requires_grad for p in model.parameters()))
            self.assertEqual('facebookresearch/dinov2:'+DINOV2_REVISION,loader.call_args.args[0])
            self.assertTrue(loader.call_args.kwargs['pretrained'])

    def test_dino_save_load_and_reject_mismatched_contract(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder, patch('card_condition.observation_backbone.torch.hub.load',side_effect=lambda *a,**k:FakeDino()):
            root=Path(folder).resolve()
            manifest,_=test_visibility_model.VisibilityModelTest().setup_data(root)
            before=manifest.read_bytes()
            report=experiment(manifest,root/'dino',device='cpu',pretrained=False,centroid=True,backbone_name='dinov2_vits14')
            analyzer=VisibilityAnalyzer(root/'dino/model.pt','cpu')
            self.assertEqual(384,report['feature_dimension'])
            for row in report['predictions']:
                self.assertAlmostEqual(row['probabilities'][TARGET],analyzer.analyze(row['image'],row['box'])['observation_limit_score'],places=6)
            self.assertEqual(before,manifest.read_bytes())
            meta=torch.load(root/'dino/model.pt',weights_only=True)
            meta['backbone_revision']='changed'
            torch.save(meta,root/'invalid.pt')
            with self.assertRaisesRegex(ValueError,'Unsupported DINOv2'):
                VisibilityAnalyzer(root/'invalid.pt','cpu')
            with self.assertRaisesRegex(ValueError,'requires centroid'):
                experiment(manifest,root/'tiles',device='cpu',centroid=True,tiles=True,backbone_name='dinov2_vits14')

    def test_legacy_mobile_checkpoint_without_backbone_metadata(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,_=test_visibility_model.VisibilityModelTest().setup_data(root)
            report=experiment(manifest,root/'mobile',device='cpu',pretrained=False,centroid=True)
            meta=torch.load(root/'mobile/model.pt',weights_only=True)
            for key in ('backbone_name','backbone_revision'):
                meta.pop(key)
            torch.save(meta,root/'legacy.pt')
            analyzer=VisibilityAnalyzer(root/'legacy.pt','cpu')
            row=report['predictions'][0]
            self.assertAlmostEqual(row['probabilities'][TARGET],analyzer.analyze(row['image'],row['box'])['observation_limit_score'],places=6)
