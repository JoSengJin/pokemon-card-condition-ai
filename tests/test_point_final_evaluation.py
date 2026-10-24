"""Exercise final evaluation with a trained tiled checkpoint and human point labels."""
import json
from pathlib import Path
import tempfile
import unittest

import torch

from test_pipeline import fixture
from card_condition.region_experiment import experiment
from card_condition.region_evaluation import evaluate_regions
from card_condition.region_model import RegionAnalyzer
from card_condition.point_dataset import point_rows


class PointFinalEvaluationTest(unittest.TestCase):
    def test_tiles_use_points_without_global_grade_and_mask_unknowns(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            _, rows = fixture(root)
            for i, row in enumerate(rows):
                row['labels'] = {key: None for key in row['labels']}
                row['side_annotations'] = {}
                for side in ('front', 'back'):
                    labels = dict(row['labels'], edge_defect=i % 2)
                    annotation = dict(image=str(root / row[side]), box=[0, 0, 1, 1], labels=labels)
                    if i % 2:
                        annotation['defect_points'] = [dict(label='edge_defect', x=.1, y=.1),
                                                     dict(label='edge_defect', x=.2, y=.2)]
                    else:
                        annotation['region_labels'] = {'upper_left': dict(
                            corner_defect=None, edge_defect=0, surface_defect=None)}
                    row['side_annotations'][side] = annotation
            development, test = root / 'development.jsonl', root / 'test.jsonl'
            development.write_text('\n'.join(json.dumps(r) for r in rows[:4]))
            test.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            experiment(development, root / 'run', epochs=1, device='cpu', pretrained=False,
                       point_grid=True, edge_input='tiles', balance=True)
            checkpoint = root / 'run/model.pt'
            before = test.read_bytes()
            report = evaluate_regions(test, checkpoint, root / 'final.json', [development], 'cpu')
            self.assertEqual('point_final', report['evaluation_kind'])
            self.assertEqual(4, report['n_regions'])  # Two clicks in one region count once.
            self.assertEqual(4, report['rates_at_05']['edge_defect']['scored'])
            self.assertEqual(2, report['rates_at_05']['edge_defect']['positive'])
            self.assertEqual(2, report['rates_at_05']['edge_defect']['negative'])
            expected, _ = point_rows(test, grid=True, splits={'test'})
            analyzer = RegionAnalyzer(checkpoint, 'cpu')
            for actual, row in zip(report['predictions'], expected):
                prediction = analyzer.analyze(row['image'], row['card_box'], row['area'])
                self.assertAlmostEqual(prediction['probabilities']['edge_defect'],
                                       actual['probabilities']['edge_defect'], places=7)
                self.assertIsNone(actual['probabilities']['surface_defect'])
            summary = report['group_error_rates_at_05']['edge_defect']
            self.assertEqual(1, summary['positive_groups'])
            self.assertEqual(1, summary['negative_groups'])
            for key in ('tp', 'tn', 'fp', 'fn'):
                self.assertEqual(report['metrics']['edge_defect'][key],
                    sum(group['edge_defect'][key] for group in report['by_group'].values()))
                self.assertEqual(report['metrics']['edge_defect'][key],
                    sum(side['edge_defect'][key] for side in report['by_group_side'].values()))
            self.assertEqual(2, len(report['by_group']))
            self.assertEqual(4, len(report['by_group_side']))
            self.assertEqual(before, test.read_bytes())
            self.assertFalse(report['production_ready'])
            self.assertEqual(0, report['actual_calls_saved'])
            # Labels for an unsupported task cannot create a successful zero-score report.
            for row in rows[4:]:
                for annotation in row['side_annotations'].values():
                    annotation['labels']['edge_defect'] = None
                    annotation['labels']['surface_defect'] = 1
                    annotation.pop('region_labels', None)
                    annotation['defect_points'] = [dict(label='surface_defect', x=.1, y=.1)]
            test.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            with self.assertRaisesRegex(ValueError, 'No scored supported'):
                evaluate_regions(test, checkpoint, root / 'empty.json', [development], 'cpu')
            self.assertFalse((root / 'empty.json').exists())
