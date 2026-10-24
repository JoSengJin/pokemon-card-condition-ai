import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import torch
import test_visibility_model
from card_condition.observation_scaling import fit_scaling,apply_scaling,validate_scaling
from card_condition.visibility_model import experiment,VisibilityAnalyzer,TARGET


class ObservationScalingTest(unittest.TestCase):
    def test_group_balance_constant_dimensions_and_invalid_statistics(self):
        x=torch.tensor([[0.,3.],[0.,3.],[4.,3.]])
        scaling=fit_scaling(x,['a','a','b'])
        torch.testing.assert_close(scaling['mean'],torch.tensor([2.,3.]))
        torch.testing.assert_close(scaling['scale'],torch.tensor([2.,1e-6]))
        torch.testing.assert_close(apply_scaling(x,scaling),torch.tensor([[-1.,0.],[-1.,0.],[1.,0.]]))
        self.assertIs(x,apply_scaling(x,None))
        for invalid in (None,dict(scaling,policy='val_fit'),dict(scaling,scale=torch.zeros(2)),
                        dict(scaling,mean=torch.tensor([float('nan'),0.])),dict(scaling,mean=torch.zeros(3))):
            with self.assertRaises(ValueError):validate_scaling(invalid,2)

    def test_validation_image_and_truth_cannot_change_scaler_or_centroid(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            before=manifest.read_bytes()
            report=experiment(manifest,root/'first',device='cpu',pretrained=False,
                              centroid=True,local_signals=True,standardize=True)
            self.assertEqual(before,manifest.read_bytes())
            self.assertEqual('train_group_standard_v1',report['feature_scaling'])
            model=VisibilityAnalyzer(root/'first/model.pt','cpu')
            for row in report['predictions']:
                self.assertAlmostEqual(row['probabilities'][TARGET],
                    model.analyze(row['image'],row['box'])['observation_limit_score'],places=6)
            for row in rows:
                if row['split']=='val':
                    Image.new('RGB',(200,300),'red').save(row['front'])
                    a=row['side_annotations']['front']
                    a['visibility_issues']=[] if a['visibility_issues'] else ['glare']
                    a['labels']['gradable']=0 if a['visibility_issues'] else 1
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            experiment(manifest,root/'changed',device='cpu',pretrained=False,
                       centroid=True,local_signals=True,standardize=True)
            changed=VisibilityAnalyzer(root/'changed/model.pt','cpu')
            for key in ('mean','scale'):
                torch.testing.assert_close(model.scaling[key],changed.scaling[key],rtol=0,atol=0)
            for key,value in model.head.state_dict().items():
                torch.testing.assert_close(value,changed.head.state_dict()[key],rtol=0,atol=0)
            meta=torch.load(root/'first/model.pt',weights_only=True)
            meta['feature_scaling']['scale'][0]=0
            torch.save(meta,root/'invalid.pt')
            with self.assertRaisesRegex(ValueError,'scaling'):
                VisibilityAnalyzer(root/'invalid.pt','cpu')

    def test_scaling_requires_registered_input_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'requires local'):
                experiment('missing.jsonl',Path(folder)/'out',standardize=True)
            with self.assertRaisesRegex(ValueError,'boolean'):
                experiment('missing.jsonl',Path(folder)/'out',standardize='yes')
