import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import torch
from test_pipeline import fixture
from card_condition.side_model import backbone_for
from card_condition.region_experiment import experiment


class SurfaceZeroTest(unittest.TestCase):
    def test_seed_independence_with_fixed_features_and_api_roundtrip(self):
        from card_condition.region_model import RegionAnalyzer
        torch.set_num_threads(1)
        def fixed_backbone(name, pretrained):
            torch.manual_seed(2024)
            return backbone_for(name,False)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i,row in enumerate(rows[:4]):
                row['labels']['surface_defect']=i%2
                a=dict(image=str(root/row['front']),box=[0,0,1,1],labels=dict(row['labels']),region_labels={})
                if i%2:a['defect_points']=[dict(label='surface_defect',x=.1,y=.1)]
                else:a['region_labels']={'upper_left':dict(corner_defect=None,edge_defect=None,surface_defect=0)}
                row['side_annotations']={'front':a}
            for row in rows[4:]:row['front']='unreadable-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            reports=[]
            for seed in [42,7]:
                output=root/str(seed)
                with patch('card_condition.region_experiment.backbone_for',side_effect=fixed_backbone):
                    r=experiment(manifest,output,point_grid=True,surface_input='context',zero_init_head=True,seed=seed,epochs=2,device='cpu',balance=True,balanced_selection=True,pretrained=False)
                self.assertEqual(r['head_initialization'],'zero')
                model=RegionAnalyzer(output/'model.pt','cpu')
                for row in r['predictions']:
                    actual=model.analyze(row['image'],row['card_box'],row['area'])
                    self.assertAlmostEqual(actual['probabilities']['surface_defect'],row['probabilities']['surface_defect'],places=6)
                reports.append(r)
            self.assertEqual(reports[0]['history'],reports[1]['history'])
            self.assertEqual(reports[0]['predictions'],reports[1]['predictions'])

    def test_invalid_combinations_rejected_before_reading_data(self):
        with tempfile.TemporaryDirectory() as folder:
            for extra in ({},{'surface_input':'context','fine_tune_spatial':True}):
                with self.assertRaises(ValueError):experiment('not-read',Path(folder)/'run',point_grid=True,zero_init_head=True,**extra)
            with self.assertRaises(ValueError):experiment('not-read',Path(folder)/'run',zero_init_head=1)
