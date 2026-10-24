import copy
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import torch

from card_condition.edge_views import edge_view_boxes, fixed_tile_boxes, patch_features, batched_patch_features
from card_condition.region_experiment import experiment
from card_condition.region_model import RegionAnalyzer
from card_condition.point_probe import point_probe, load_probe_model
from card_condition.point_benchmark import benchmark_points
from card_condition.regions import GLARE_AREAS, region_box
from card_condition.side_model import backbone_for
from test_pipeline import fixture


class EdgeViewsTest(unittest.TestCase):
    def test_geometry_keeps_outer_edges_and_full_context(self):
        card = [.1, .2, .9, .95]
        for area in GLARE_AREAS:
            patch = region_box(card, area)
            row = dict(card_box=card, box=patch, area=area)
            boxes = edge_view_boxes(row)
            self.assertEqual(0 if area == 'center' else 1 if 'center' in area or area.startswith('middle') else 2, len(boxes))
            for left, top, right, bottom in boxes:
                self.assertTrue(patch[0] <= left < right <= patch[2])
                self.assertTrue(patch[1] <= top < bottom <= patch[3])
                self.assertTrue(left == card[0] or top == card[1] or right == card[2] or bottom == card[3])
            self.assertEqual(patch, row['box'])
            tiles = fixed_tile_boxes(row)
            self.assertEqual(4, len(tiles))
            self.assertAlmostEqual((patch[2]-patch[0])*(patch[3]-patch[1]),
                sum((b[2]-b[0])*(b[3]-b[1]) for b in tiles))
            self.assertTrue(all(patch[0] <= b[0] < b[2] <= patch[2] and patch[1] <= b[1] < b[3] <= patch[3] for b in tiles))
            self.assertEqual(tiles, fixed_tile_boxes({**row, 'defect_points':[{'x':.99,'y':.99}]}))

    def test_training_probe_policy_and_leakage(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for i, row in enumerate(rows[:4]):
                row['labels']['gradable'] = None
                annotation = dict(image=str(root/row['front']), box=[0, 0, 1, 1], labels=dict(row['labels']))
                if i % 2:
                    annotation['defect_points'] = [dict(label='edge_defect', x=.02, y=.02)]
                else:
                    annotation['region_labels'] = {'upper_left': dict(corner_defect=None, edge_defect=0, surface_defect=None)}
                row['side_annotations'] = {'front': annotation}
            for row in rows[4:]:
                row['front'] = 'missing-final-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            original = manifest.read_bytes()
            for mode in ('context', 'views', 'tiles'):
                size = 448 if mode == 'views' else 224
                report = experiment(manifest, root/mode, epochs=2, device='cpu', pretrained=False,
                                    point_grid=True, balance=True, edge_input=mode, image_size=size)
                self.assertEqual(size, report['image_size'])
                analyzer=RegionAnalyzer(root/mode/'model.pt','cpu')
                for prediction in report['predictions']:
                    for batch in (False,True):
                        actual=analyzer.analyze(prediction['image'],prediction['card_box'],
                            prediction['area'],batch_views=batch)
                        self.assertAlmostEqual(prediction['probabilities']['edge_defect'],
                            actual['probabilities']['edge_defect'],places=6)
                        self.assertEqual(size,actual['image_size'])
                        self.assertEqual(mode,actual['input_policy'])
                        self.assertEqual(batch,actual['batched_views'])
                        masked=analyzer.analyze(prediction['image'],prediction['card_box'],
                            prediction['area'],unknown_labels=['edge_defect'],batch_views=batch)
                        self.assertIsNone(masked['probabilities']['edge_defect'])
                        self.assertEqual('observation_limited',masked['null_reasons']['edge_defect'])
                        self.assertFalse(masked['production_ready'])

                self.assertEqual(['edge_defect'], report['supported'])
                self.assertEqual(2, sum(report['metrics']['edge_defect'].values()))
                self.assertTrue(all(p['probabilities']['surface_defect'] is None for p in report['predictions']))
                timing = benchmark_points(manifest, root/mode/'model.pt', root/(mode+'-timing.json'), 'cpu')
                self.assertEqual(2, timing['n_patches'])
                self.assertEqual(6, timing['samples'])
                self.assertGreater(timing['median_seconds'], 0)
                self.assertLessEqual(timing['min_seconds'], timing['p95_seconds'])
                self.assertFalse(timing['production_ready'])
                self.assertEqual(size, timing['image_size'])
                with self.assertRaisesRegex(ValueError, 'Output exists'):
                    benchmark_points(manifest, root/mode/'model.pt', root/(mode+'-timing.json'))
            meta, backbone, head, policy = load_probe_model(root/'tiles/model.pt')
            self.assertEqual('tiles', policy)
            self.assertEqual('full_3x3_plus_fixed_2x2_max_features_v1', json.loads((root/'tiles/report.json').read_text())['crop_policy'])
            for prediction in json.loads((root/'tiles/report.json').read_text())['predictions']:
                with torch.inference_mode():
                    score = head(patch_features(backbone, prediction, 'cpu', policy)).sigmoid()[0,1].item()
                self.assertAlmostEqual(score, prediction['probabilities']['edge_defect'], places=6)
            meta['edge_input']='context'
            torch.save(meta,root/'bad-tiles.pt')
            with self.assertRaisesRegex(ValueError, 'tile checkpoint policy'):
                load_probe_model(root/'bad-tiles.pt')
            self.assertEqual(original, manifest.read_bytes())
            fresh = copy.deepcopy(rows[2])
            fresh.update(id='fresh', group='fresh', front=str(root/'fresh.png'))
            Image.new('RGB', (90, 130), (13, 111, 231)).save(fresh['front'])
            fresh['side_annotations']['front']['image'] = fresh['front']
            probe_manifest = root/'probe.jsonl'
            probe_manifest.write_text(json.dumps(fresh))
            result = point_probe(probe_manifest, [root/'views/model.pt'], root/'probe.json', ['fresh'], [manifest])
            self.assertEqual(1, result['regions'])
            meta = torch.load(root/'views/model.pt', weights_only=True)
            backbone, dim = backbone_for('mobilenet_v3_small')
            backbone.load_state_dict(meta['backbone'])
            with torch.inference_mode():
                features = patch_features(backbone, result['reports'][0]['predictions'][0], 'cpu', True, meta['image_size'])
            self.assertEqual((1, dim*2), tuple(features.shape))
            head = torch.nn.Linear(dim*2, 3)
            head.load_state_dict(meta['head'])
            with torch.inference_mode():
                expected = head(features).sigmoid()[0, 1].item()
            self.assertAlmostEqual(expected, result['reports'][0]['predictions'][0]['probabilities']['edge_defect'], places=6)
            with self.assertRaisesRegex(ValueError, 'Development'):
                point_probe(manifest, [root/'views/model.pt'], root/'leak.json', ['2'], [manifest])
            meta['edge_input'] = 'context'
            torch.save(meta, root/'bad.pt')
            with self.assertRaisesRegex(ValueError, 'policy'):
                point_probe(probe_manifest, [root/'bad.pt'], root/'bad.json', ['fresh'], [manifest])
            meta['edge_input'] = 'views'
            meta['image_size'] = 123
            torch.save(meta, root/'bad.pt')
            with self.assertRaisesRegex(ValueError, 'image_size'):
                load_probe_model(root/'bad.pt')
            del meta['image_size']
            torch.save(meta, root/'legacy.pt')
            self.assertNotIn('image_size', load_probe_model(root/'legacy.pt')[0])
            with self.assertRaisesRegex(ValueError, 'Edge input'):
                experiment(manifest, root/'invalid', edge_input='views')


class BatchedViewsTest(unittest.TestCase):
    def test_same_views_and_pooling_with_one_backbone_call(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'pattern.png'
            Image.effect_noise((137,191),50).convert('RGB').save(image)
            backbone,_=backbone_for('mobilenet_v3_small')
            for policy in (False,True,'tiles','tiles-max'):
                for area in ('upper_left','center'):
                    row=dict(image=str(image),card_box=[0,0,1,1],area=area,box=region_box([0,0,1,1],area))
                    sizes=[]
                    handle=backbone.register_forward_pre_hook(lambda module,args: sizes.append(args[0].shape[0]))
                    with torch.inference_mode():
                        expected=patch_features(backbone,row,'cpu',policy)
                        sizes.clear()
                        actual=batched_patch_features(backbone,row,'cpu',policy)
                    handle.remove()
                    torch.testing.assert_close(actual,expected,rtol=1e-4,atol=1e-6)
                    self.assertEqual(1,len(sizes))
                    self.assertEqual(5 if policy in ('tiles','tiles-max') else
                        3 if policy and area=='upper_left' else 1,sizes[0])
            with self.assertRaisesRegex(ValueError,'inference mode'):
                batched_patch_features(backbone,row,'cpu','tiles')
            with torch.no_grad(), self.assertRaisesRegex(ValueError,'inference mode'):
                batched_patch_features(backbone,row,'cpu','tiles')
            backbone.train()
            with torch.inference_mode(), self.assertRaisesRegex(ValueError,'eval backbone'):
                batched_patch_features(backbone,row,'cpu','tiles')
