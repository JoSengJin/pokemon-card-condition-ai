import copy
import json
from pathlib import Path
import tempfile
import unittest

import torch

from test_pipeline import fixture
from card_condition.region_experiment import experiment
from card_condition.region_evaluation import evaluate_regions


class RegionEvaluationTest(unittest.TestCase):
    def test_unseen_only_unknown_mask_and_history_leakage(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            _, rows = fixture(root)
            for row in rows:
                row['side_annotations'] = {'front': {
                    'image':str(root / row['front']), 'box':[0, 0, 1, 1], 'labels':dict(row['labels']),
                    'region_labels':{'upper_left':{'corner_defect':row['labels']['corner_defect'],
                                                  'edge_defect':None, 'surface_defect':None}}}}
            development = root / 'development.jsonl'
            development.write_text(''.join(json.dumps(r)+'\n' for r in rows[:4]))
            experiment(development, root / 'run', epochs=1, device='cpu', pretrained=False)
            checkpoint = root / 'run/model.pt'
            test = root / 'test.jsonl'
            test.write_text(''.join(json.dumps(r)+'\n' for r in rows[4:]))
            output = root / 'final.json'
            report = evaluate_regions(test, checkpoint, output, [development], 'cpu')
            self.assertEqual('region_final', report['evaluation_kind'])
            self.assertEqual(2, report['n_cards'])
            self.assertEqual(2, sum(report['metrics']['corner_defect'].values()))
            self.assertIsNone(report['predictions'][0]['probabilities']['surface_defect'])
            self.assertEqual('observation_limited', report['predictions'][0]['null_reasons']['surface_defect'])
            self.assertTrue(report['requires_gemini'])
            self.assertFalse(report['production_ready'])
            with self.assertRaisesRegex(ValueError, 'exists'):
                evaluate_regions(test, checkpoint, output, [development], 'cpu')
            with self.assertRaisesRegex(ValueError, 'history'):
                evaluate_regions(test, checkpoint, root / 'missing.json', [], 'cpu')
            with self.assertRaisesRegex(ValueError, 'test-only'):
                evaluate_regions(development, checkpoint, root / 'mixed.json', [development], 'cpu')
            for key, value in (('id', '0'), ('group', '0'), ('front', rows[0]['front'])):
                candidate = copy.deepcopy(rows[4])
                candidate[key] = value
                candidate['side_annotations']['front']['image'] = str(root / candidate['front'])
                test.write_text(json.dumps(candidate)+'\n')
                with self.assertRaisesRegex(ValueError, 'Development'):
                    evaluate_regions(test, checkpoint, root / 'leak.json', [development], 'cpu')
                self.assertFalse((root / 'leak.json').exists())
            # An older experiment also counts, even when the current checkpoint never saw it.
            prior = copy.deepcopy(rows[4]); prior['split'] = 'val'
            history = root / 'older.jsonl'; history.write_text(json.dumps(prior)+'\n')
            test.write_text(json.dumps(rows[4])+'\n')
            with self.assertRaisesRegex(ValueError, 'Development'):
                evaluate_regions(test, checkpoint, root / 'old-leak.json', [development, history], 'cpu')
