import json
from pathlib import Path
import tempfile
import unittest

import torch

from card_condition.edge_views import fixed_tile_boxes, patch_features
from card_condition.side_experiment import side_tensor
from card_condition.side_model import backbone_for
from card_condition.region_experiment import experiment
from card_condition.region_model import RegionAnalyzer
from card_condition.point_probe import load_probe_model
from card_condition.listing_inference import infer_listings
from test_pipeline import fixture


class TileMaxTest(unittest.TestCase):
    def test_only_tile_spatial_pool_changes_full_view_stays_average(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            row=dict(image=str(root/rows[0]['front']),box=[0,0,1,1])
            backbone=torch.nn.Identity()
            boxes=fixed_tile_boxes(row)
            full=side_tensor(row['image'],row['box'],True).mean((1,2)).unsqueeze(0)
            tiles=[side_tensor(row['image'],b,True) for b in boxes]
            expected_max=torch.stack([t.amax((1,2)) for t in tiles]).amax(0).unsqueeze(0)
            expected_avg=torch.stack([t.mean((1,2)) for t in tiles]).amax(0).unsqueeze(0)
            actual=patch_features(backbone,row,'cpu','tiles-max')
            baseline=patch_features(backbone,row,'cpu','tiles')
            torch.testing.assert_close(actual,torch.cat((full,expected_max),1))
            torch.testing.assert_close(baseline,torch.cat((full,expected_avg),1))
            self.assertTrue(torch.equal(actual[:,:3],baseline[:,:3]))
            self.assertFalse(torch.equal(actual[:,3:],baseline[:,3:]))

    def test_saved_policy_reproduces_scores_and_never_opens_test(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i,row in enumerate(rows[:4]):
                row['front']=str(root/row['front']);row['back']=str(root/row['back'])
                row['side_annotations']={'front':dict(image=row['front'],box=[0,0,1,1],
                    labels=dict(row['labels']),visibility_issues=[],region_labels={'upper_left':
                    dict(corner_defect=None,edge_defect=i%2,surface_defect=None)})}
                if i%2:row['side_annotations']['front']['defect_points']=[dict(label='edge_defect',x=.1,y=.1)]
            for row in rows[4:]:row['front']='must-not-open-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows));before=manifest.read_bytes()
            torch.manual_seed(42);initial,_=backbone_for('mobilenet_v3_small')
            report=experiment(manifest,root/'model',epochs=3,device='cpu',pretrained=False,
                point_grid=True,balance=True,edge_input='tiles-max',balanced_selection=True)
            meta,backbone,head,policy=load_probe_model(root/'model/model.pt')
            self.assertEqual('tiles-max',policy)
            self.assertEqual(['edge_defect'],meta['supported'])
            self.assertTrue(all(torch.equal(v,backbone.state_dict()[k]) for k,v in initial.state_dict().items()))
            for p in report['predictions']:
                with torch.inference_mode():value=head(patch_features(backbone,p,'cpu',policy)).sigmoid()[0,1].item()
                self.assertAlmostEqual(value,p['probabilities']['edge_defect'],places=6)
                api=RegionAnalyzer(root/'model/model.pt','cpu')
                actual=api.analyze(p['image'],p['card_box'],p['area'],batch_views=True)
                self.assertEqual('tiles-max',actual['input_policy'])
                self.assertAlmostEqual(value,actual['probabilities']['edge_defect'],places=6)

            listing=infer_listings(manifest,root/'model/model.pt',root/'listing.json','cpu')
            self.assertEqual(16,listing['inferred_regions'])
            self.assertEqual(0,listing['actual_calls_saved'])
            self.assertEqual(before,manifest.read_bytes())
            meta['edge_input']='tiles';torch.save(meta,root/'bad.pt')
            with self.assertRaisesRegex(ValueError,'tile checkpoint'):
                load_probe_model(root/'bad.pt')
            with self.assertRaisesRegex(ValueError,'Spatial fine-tuning'):
                experiment(manifest,root/'bad-model',point_grid=True,edge_input='tiles-max',fine_tune_spatial=True)
