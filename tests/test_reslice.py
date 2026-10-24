import json
from pathlib import Path
import tempfile
import unittest

import torch
from PIL import Image

from test_pipeline import fixture
from card_condition.reslice import reslice
from card_condition.side_experiment import experiment


class ResliceTest(unittest.TestCase):
    def test_diagnostic_edits_are_resliced_without_retraining(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            reference, rows = fixture(root)
            for row in rows:
                row['side_annotations'] = {side: {'image': str(root / row[side]), 'box': [0, 0, 1, 1],
                                                  'labels': dict(row['labels'])} for side in ('front', 'back')}
            reference.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            trained = root / 'trained'
            original = experiment(reference, trained, device='cpu', epochs=1, pretrained=False)
            rows[2]['side_annotations']['front']['visibility_issues'] = ['glare']
            rows[2]['side_annotations']['front']['glare_areas'] = ['lower_right', 'center']
            updated = root / 'updated.jsonl'
            updated.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            output = root / 'resliced.json'
            result = reslice(reference, updated, trained / 'report.json', trained / 'model.pt', output)
            self.assertEqual(1, result['visibility_counts']['val']['glare'])
            self.assertEqual(1, result['glare_area_counts']['val']['lower_right'])
            self.assertEqual(1, result['glare_location_coverage']['val']['located'])
            self.assertEqual([], result['glare_location_coverage']['val']['unlocated_ids'])
            self.assertEqual(result['visibility_validation_metrics']['glare'],
                             result['glare_area_validation_metrics']['lower_right'])
            self.assertTrue(result['resliced_without_retraining'])
            self.assertEqual(original['predictions'], json.loads(output.read_text())['predictions'])
            self.assertEqual(original['metrics'], json.loads(output.read_text())['metrics'])
            with self.assertRaisesRegex(ValueError, 'exists'):
                reslice(reference, updated, trained / 'report.json', trained / 'model.pt', output)
            rows[2]['side_annotations']['front']['labels']['gradable'] = 1 - rows[2]['side_annotations']['front']['labels']['gradable']
            updated.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'inputs changed'):
                reslice(reference, updated, trained / 'report.json', trained / 'model.pt', root / 'bad.json')
            rows[2]['side_annotations']['front']['labels']['gradable'] = 0
            updated.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            Image.new('RGB', (90, 130), 'black').save(root / '2-front.png')
            with self.assertRaisesRegex(ValueError, 'pixels differ'):
                reslice(reference, updated, trained / 'report.json', trained / 'model.pt', root / 'bad.json')
