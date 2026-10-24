import json
from pathlib import Path
import tempfile
import unittest

import torch

from card_condition.edge_views import patch_features, tile_prefix_maps, tile_tail_features
from card_condition.point_probe import load_probe_model
from card_condition.region_experiment import experiment
from card_condition.side_model import backbone_for
from test_pipeline import fixture


class PointSpatialTest(unittest.TestCase):
    def test_only_spatial_block_updates_and_saved_model_matches_report(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for i, row in enumerate(rows[:4]):
                row['side_annotations'] = {'front': dict(image=str(root/row['front']),
                    box=[0,0,1,1], labels=dict(row['labels']), region_labels={'upper_left':
                    dict(corner_defect=None,edge_defect=i%2,surface_defect=None)})}
                if i%2:
                    row['side_annotations']['front']['defect_points'] = [dict(label='edge_defect',x=.1,y=.1)]
            for row in rows[4:]:
                row['front'] = 'must-not-read-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            torch.manual_seed(42)
            initial, _ = backbone_for('mobilenet_v3_small')
            report = experiment(manifest, root/'model', epochs=3, device='cpu', pretrained=False,
                point_grid=True, balance=True, edge_input='context', fine_tune_spatial=True)
            meta, backbone, head, views = load_probe_model(root/'model/model.pt')
            self.assertTrue(meta['fine_tune_spatial'])
            self.assertTrue(report['fine_tune_spatial'])
            self.assertEqual(before, manifest.read_bytes())
            original, current = initial.state_dict(), backbone.state_dict()
            changed = [key for key in original if not torch.equal(original[key], current[key])]
            self.assertTrue(changed)
            block_prefix = str(len(initial)-2)+'.'
            self.assertTrue(all(key.startswith(block_prefix) for key in changed))
            self.assertFalse(any('running_' in key or 'num_batches_tracked' in key for key in changed))
            for prediction in report['predictions']:
                with torch.inference_mode():
                    value = head(patch_features(backbone,prediction,'cpu',views)).sigmoid()[0,1].item()
                self.assertAlmostEqual(value, prediction['probabilities']['edge_defect'], places=6)
            self.assertEqual(min(h['val'] for h in report['history']), report['best_validation_loss'])
            with self.assertRaisesRegex(ValueError, 'Spatial fine-tuning'):
                experiment(manifest, root/'bad', fine_tune_spatial=True)

    def test_fixed_tile_cache_matches_inference_and_only_spatial_block_learns(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for i, row in enumerate(rows[:4]):
                row['side_annotations'] = {'front': dict(image=str(root/row['front']),
                    box=[0,0,1,1],labels=dict(row['labels']),region_labels={'upper_left':
                    dict(corner_defect=None,edge_defect=i%2,surface_defect=None)})}
                if i%2:
                    row['side_annotations']['front']['defect_points']=[dict(label='edge_defect',x=.1,y=.1)]
            for row in rows[4:]: row['front']='must-not-read-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before=manifest.read_bytes()
            torch.manual_seed(42)
            initial,_=backbone_for('mobilenet_v3_small')
            row=dict(image=str(root/rows[0]['front']),box=[0,0,.33,.33])
            with torch.no_grad():
                cached=tile_prefix_maps(initial[:-2],row,'cpu')
                actual=tile_tail_features(initial[-2:],cached)
                expected=patch_features(initial,row,'cpu','tiles')
            torch.testing.assert_close(actual,expected,atol=1e-6,rtol=1e-5)
            initial[-2].requires_grad_(True)
            tile_tail_features(initial[-2:],cached).sum().backward()
            self.assertTrue(any(p.grad is not None for p in initial[-2].parameters()))
            self.assertTrue(all(p.grad is None for p in initial[:-2].parameters()))
            report=experiment(manifest,root/'model',epochs=3,device='cpu',pretrained=False,
                point_grid=True,balance=True,edge_input='tiles',fine_tune_spatial=True,balanced_selection=True)
            meta,backbone,head,views=load_probe_model(root/'model/model.pt')
            self.assertEqual('tiles',views)
            self.assertTrue(meta['fine_tune_spatial'])
            self.assertEqual(before,manifest.read_bytes())
            original,current=initial.state_dict(),backbone.state_dict()
            changed=[k for k in original if not torch.equal(original[k],current[k])]
            self.assertTrue(changed)
            self.assertTrue(all(k.startswith(str(len(initial)-2)+'.') for k in changed))
            self.assertFalse(any('running_' in k or 'num_batches_tracked' in k for k in changed))
            for prediction in report['predictions']:
                with torch.inference_mode():
                    value=head(patch_features(backbone,prediction,'cpu',views)).sigmoid()[0,1].item()
                self.assertAlmostEqual(value,prediction['probabilities']['edge_defect'],places=6)
            self.assertEqual(min(h['val'] for h in report['history']),report['best_validation_loss'])
