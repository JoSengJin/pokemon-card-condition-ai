import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import torch
import test_visibility_model
from card_condition.observation_signals import local_color_texture
from card_condition.visibility_model import experiment, VisibilityAnalyzer, TARGET


class LocalSignalsTest(unittest.TestCase):
    def test_fixed_descriptor_preserves_cell_location(self):
        white=Image.new('RGB',(224,224),'white')
        self.assertEqual([1.,0.,0.,1.]*9,local_color_texture(white))
        white.paste('blue',(0,0,74,74))
        values=local_color_texture(white)
        self.assertEqual(36,len(values))
        self.assertEqual([1.,0.],values[2:4])
        self.assertEqual([1.,0.,0.,1.]*8,values[4:])
        with self.assertRaisesRegex(ValueError,'224px'):
            local_color_texture(Image.new('RGB',(448,448)))

    def test_checkpoint_roundtrip_and_validation_truth_independence(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            original=manifest.read_bytes()
            report=experiment(manifest,root/'local',device='cpu',pretrained=False,
                              centroid=True,local_signals=True)
            self.assertEqual(612,report['input_feature_dimension'])
            analyzer=VisibilityAnalyzer(root/'local/model.pt','cpu')
            for row in report['predictions']:
                self.assertAlmostEqual(row['probabilities'][TARGET],
                    analyzer.analyze(row['image'],row['box'])['observation_limit_score'],places=6)
            self.assertEqual(original,manifest.read_bytes())
            for row in rows:
                if row['split']=='val':
                    a=row['side_annotations']['front']
                    a['visibility_issues']=[] if a['visibility_issues'] else ['glare']
                    a['labels']['gradable']=0 if a['visibility_issues'] else 1
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            experiment(manifest,root/'swapped',device='cpu',pretrained=False,
                       centroid=True,local_signals=True)
            changed=VisibilityAnalyzer(root/'swapped/model.pt','cpu')
            for key,value in analyzer.head.state_dict().items():
                torch.testing.assert_close(value,changed.head.state_dict()[key],rtol=0,atol=0)
            meta=torch.load(root/'local/model.pt',weights_only=True)
            for key,value in [('local_signals','yes'),('input_policy','tiles'),('head_policy','linear')]:
                invalid=dict(meta); invalid[key]=value
                torch.save(invalid,root/'invalid.pt')
                with self.assertRaisesRegex(ValueError,'Unsupported'):
                    VisibilityAnalyzer(root/'invalid.pt','cpu')

    def test_mixed_hypotheses_refused_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            for args in ({},{'tiles':True,'centroid':True},{'interior':True,'centroid':True},
                         {'backbone_name':'dinov2_vits14','centroid':True}):
                with self.assertRaisesRegex(ValueError,'Local signals require'):
                    experiment('missing.jsonl',Path(folder)/'out',local_signals=True,**args)
            with self.assertRaisesRegex(ValueError,'boolean'):
                experiment('missing.jsonl',Path(folder)/'out',local_signals=1)
