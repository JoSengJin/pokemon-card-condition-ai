import json
import hashlib
from pathlib import Path
import tempfile
import unittest

import torch

from test_pipeline import fixture
from card_condition.region_experiment import experiment, group_training_weights
from card_condition.side_model import backbone_for
from card_condition.side_experiment import side_tensor
from card_condition.region_model import RegionAnalyzer
from card_condition.regions import region_box
from card_condition.comparison import compare_regions, group_error_rates


class RegionExperimentTest(unittest.TestCase):
    def test_group_rates_equal_card_weight_and_absent_classes(self):
        groups = {'many': {'edge_defect': dict(tp=2, fn=0, tn=1, fp=9)},
                  'few': {'edge_defect': dict(tp=0, fn=1, tn=1, fp=0)},
                  'unknown': {'edge_defect': dict(tp=0, fn=0, tn=0, fp=0)}}
        result = group_error_rates(groups, ['edge_defect'])['edge_defect']
        self.assertEqual(2, result['negative_groups'])
        self.assertEqual(2, result['positive_groups'])
        self.assertAlmostEqual(.45, result['mean_false_positive_rate'])
        self.assertEqual(.5, result['mean_miss_rate'])
        self.assertIsNone(group_error_rates({'unknown': groups['unknown']}, ['edge_defect'])['edge_defect']['mean_miss_rate'])

    def test_group_weights_use_only_known_training_labels(self):
        def row(group, split, value):
            return {'group': group, 'split': split, 'labels': {
                'corner_defect': value, 'edge_defect': None, 'surface_defect': 1}}
        rows = [row('a', 'train', 0), row('a', 'train', 1), row('b', 'train', 0),
                row('a', 'val', 1), row('a', 'test', 1), row('a', 'train', None)]
        weights = group_training_weights(rows, ['corner_defect'])
        self.assertEqual([[.5, 0, 0], [.5, 0, 0], [1, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], weights)
        self.assertEqual(weights[:3], group_training_weights(rows[:3], ['corner_defect']))

    def test_training_checkpoint_unknown_and_test_isolation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for row in rows[:4]:
                row['side_annotations'] = {'front': {'image': str(root / row['front']), 'box': [0, 0, 1, 1],
                    'labels': dict(row['labels']), 'region_labels': {'upper_left': {
                        'corner_defect': row['labels']['corner_defect'], 'edge_defect': None, 'surface_defect': None}}}}
            for row in rows[4:]:
                row['front'] = 'missing-test.png'
                row['side_annotations'] = {'invalid': 'must not be read'}
            manifest.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            report = experiment(manifest, root / 'run', epochs=2, device='cpu', pretrained=False)
            self.assertEqual(['corner_defect'], report['supported'])
            self.assertEqual(2, sum(report['metrics']['corner_defect'].values()))
            self.assertTrue(all(p['probabilities']['surface_defect'] is None for p in report['predictions']))
            self.assertEqual(0, report['actual_calls_saved'])
            self.assertTrue(report['requires_gemini'])
            self.assertEqual(min(h['val'] for h in report['history']), report['best_validation_loss'])
            balanced = experiment(manifest, root / 'balanced', epochs=2, device='cpu', pretrained=False,
                                  group_balance=True)
            self.assertTrue(balanced['group_balance'])
            self.assertEqual(report['history'], balanced['history'])
            self.assertEqual({'0': 1, '1': 1}, balanced['group_class_counts']['train']['corner_defect'])
            resnet = experiment(manifest, root / 'resnet', epochs=2, device='cpu', pretrained=False,
                                backbone_name='resnet18')
            rp = resnet['predictions'][0]
            ra = RegionAnalyzer(root / 'resnet/model.pt', 'cpu').analyze(rp['image'], [0, 0, 1, 1], 'upper_left')
            self.assertAlmostEqual(rp['probabilities']['corner_defect'], ra['probabilities']['corner_defect'], places=6)
            self.assertIsNone(ra['probabilities']['surface_defect'])
            comparison = compare_regions(manifest, [root / 'run/report.json', root / 'resnet/report.json'],
                                         root / 'comparison.json')
            self.assertEqual(2, comparison['regions'])
            self.assertEqual(2, comparison['groups'])
            self.assertFalse(comparison['production_ready'])
            changed_rows = json.loads(json.dumps(rows))
            changed_rows[0]['side_annotations']['front']['region_labels']['upper_left']['surface_defect'] = 0
            current_manifest = root / 'train-updated.jsonl'
            current_manifest.write_text(''.join(json.dumps(row) + '\n' for row in changed_rows))
            current_report = json.loads(json.dumps(report))
            current_report['manifest_sha256'] = hashlib.sha256(current_manifest.read_bytes()).hexdigest()
            (root / 'current-report.json').write_text(json.dumps(current_report))
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                compare_regions(current_manifest, [root / 'run/report.json', root / 'current-report.json'], root / 'no-reference.json')
            updated_comparison = compare_regions(current_manifest,
                [root / 'run/report.json', root / 'current-report.json'], root / 'updated-comparison.json', [manifest])
            self.assertEqual(2, len(updated_comparison['validated_manifests']))
            changed_rows[2]['side_annotations']['front']['box'] = [.1, .1, .9, .9]
            current_manifest.write_text(''.join(json.dumps(row) + '\n' for row in changed_rows))
            with self.assertRaisesRegex(ValueError, 'Reference validation'):
                compare_regions(current_manifest, [root / 'run/report.json'] * 2, root / 'changed-val.json', [manifest])
            for model, original in zip(comparison['models'], [report, resnet]):
                self.assertEqual(original['metrics'], model['metrics_at_05'])
                self.assertEqual(original['metrics'], model['threshold_analysis'][4]['metrics'])
                self.assertEqual(model['group_error_rates_at_05'],
                                 model['threshold_analysis'][4]['group_error_rates'])
                self.assertEqual(2, len(model['by_group']))
                rates = model['group_error_rates_at_05']['corner_defect']
                self.assertEqual(1, rates['negative_groups'])
                self.assertEqual(1, rates['positive_groups'])
                self.assertEqual(sum(v['fp'] + v['fn'] for v in original['metrics'].values()), len(model['errors']))
            with self.assertRaisesRegex(ValueError, 'exists'):
                compare_regions(manifest, [root / 'run/report.json'] * 2, root / 'comparison.json')
            for field, value in [('image_sha256', 'wrong'), ('box', [0, 0, .5, .5]),
                                 ('labels', {'corner_defect': None}), ('group', 'wrong')]:
                with self.subTest(field=field):
                    tampered = json.loads(json.dumps(report))
                    tampered['predictions'][0][field] = value
                    (root / 'tampered.json').write_text(json.dumps(tampered))
                    with self.assertRaisesRegex(ValueError, 'differ'):
                        compare_regions(manifest, [root / 'run/report.json', root / 'tampered.json'], root / 'rejected.json')
                    self.assertFalse((root / 'rejected.json').exists())
            for value in (float('nan'), None, True, 1.1):
                tampered = json.loads(json.dumps(report))
                tampered['predictions'][0]['probabilities']['corner_defect'] = value
                (root / 'tampered.json').write_text(json.dumps(tampered))
                with self.assertRaisesRegex(ValueError, 'probabilities'):
                    compare_regions(manifest, [root / 'run/report.json', root / 'tampered.json'], root / 'rejected.json')
            tampered = json.loads(json.dumps(report))
            tampered['metrics']['corner_defect']['fp'] += 1
            (root / 'tampered.json').write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, 'metrics'):
                compare_regions(manifest, [root / 'run/report.json', root / 'tampered.json'], root / 'rejected.json')
            meta = torch.load(root / 'run/model.pt', weights_only=True)
            meta.pop('backbone_name')
            torch.save(meta, root / 'legacy.pt')
            RegionAnalyzer(root / 'legacy.pt', 'cpu')
            meta['backbone_name'] = 'resnet18'
            torch.save(meta, root / 'mismatch.pt')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                RegionAnalyzer(root / 'mismatch.pt', 'cpu')
            meta.pop('backbone_name')
            self.assertEqual(report['manifest_sha256'], meta['manifest_sha256'])
            self.assertEqual(['0', '1', '2', '3'], meta['development_groups'])
            self.assertEqual(['0', '1', '2', '3'], meta['development_ids'])
            self.assertEqual(4, len(meta['development_image_hashes']))
            backbone, dimension = backbone_for('mobilenet_v3_small')
            backbone.load_state_dict(meta['backbone']); backbone.eval()
            head = torch.nn.Linear(dimension, 3); head.load_state_dict(meta['head']); head.eval()
            p = report['predictions'][0]
            with torch.inference_mode():
                probs = head(backbone(side_tensor(p['image'], p['box'], True).unsqueeze(0)).mean((2, 3))).sigmoid()[0]
            self.assertAlmostEqual(float(probs[0]), p['probabilities']['corner_defect'], places=6)
            analyzer = RegionAnalyzer(root / 'run/model.pt', 'cpu')
            actual = analyzer.analyze(p['image'], [0, 0, 1, 1], 'upper_left')
            self.assertAlmostEqual(actual['probabilities']['corner_defect'], float(probs[0]), places=6)
            self.assertIsNone(actual['probabilities']['edge_defect'])
            self.assertEqual('unsupported', actual['null_reasons']['edge_defect'])
            limited = analyzer.analyze(p['image'], [0, 0, 1, 1], 'upper_left', ['corner_defect'])
            self.assertIsNone(limited['probabilities']['corner_defect'])
            self.assertEqual('observation_limited', limited['null_reasons']['corner_defect'])
            self.assertTrue(limited['requires_gemini'])
            self.assertIsNone(analyzer.analyze(p['image'], [0, 0, 1, 1], 'center')['probabilities']['corner_defect'])
            with self.assertRaisesRegex(ValueError, 'unknown_labels'):
                analyzer.analyze(p['image'], [0, 0, 1, 1], 'upper_left', ['corner_defect', 'corner_defect'])
            with self.assertRaisesRegex(ValueError, 'required'):
                analyzer.analyze(p['image'], [0, 0, 0, 1], 'upper_left')
            with self.assertRaisesRegex(ValueError, 'required'):
                region_box([0, 0, float('nan'), 1], 'upper_left')
            meta['labels'] = ['wrong']
            torch.save(meta, root / 'invalid.pt')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                RegionAnalyzer(root / 'invalid.pt', 'cpu')
            with self.assertRaisesRegex(ValueError, 'exists'):
                experiment(manifest, root / 'run', device='cpu', pretrained=False)
            for row in rows[:4]:
                row['side_annotations']['front']['region_labels']['upper_left']['corner_defect'] = None
            manifest.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'insufficient'):
                experiment(manifest, root / 'empty', device='cpu', pretrained=False)
