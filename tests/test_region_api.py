from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import torch

from card_condition.edge_views import patch_features
from card_condition.region_model import RegionAnalyzer
from card_condition.regions import REGION_LABELS
from card_condition.side_model import backbone_for


class RegionApiTest(unittest.TestCase):
    def test_legacy_448_and_invalid_sizes(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);image=root/'photo.png'
            Image.effect_noise((151,213),50).convert('RGB').save(image)
            body,dim=backbone_for('mobilenet_v3_small');head=torch.nn.Linear(dim,3)
            meta=dict(architecture='mobilenet_v3_small_region_v1',supported=['surface_defect'],
                labels=list(REGION_LABELS),backbone=body.state_dict(),head=head.state_dict(),image_size=448)
            path=root/'model.pt';torch.save(meta,path)
            analyzer=RegionAnalyzer(path,'cpu')
            with patch('card_condition.region_model.patch_features',wraps=patch_features) as features:
                result=analyzer.analyze(image,[0,0,1,1],'center')
            self.assertEqual(448,features.call_args.args[-1])
            self.assertEqual(448,result['image_size'])
            self.assertEqual('context',result['input_policy'])
            self.assertIsNone(result['probabilities']['edge_defect'])
            self.assertEqual('not_applicable',result['null_reasons']['edge_defect'])
            for size in (True,0,123,224.0,None):
                torch.save({**meta,'image_size':size},path)
                with self.assertRaisesRegex(ValueError,'image_size'):
                    RegionAnalyzer(path,'cpu')

    def test_new_checkpoint_policy_and_provenance_remain_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.pt'
            for extra in (dict(edge_input='context'),dict(edge_input='tiles')):
                torch.save(dict(architecture='mobilenet_v3_small_point_edge_tiles_v1',
                    backbone_name='mobilenet_v3_small',supported=['edge_defect'],
                    labels=list(REGION_LABELS),backbone={},head={},**extra),path)
                with self.assertRaises(ValueError):
                    RegionAnalyzer(path,'cpu')
            torch.save(dict(backbone_name=3),path)
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                RegionAnalyzer(path,'cpu')
