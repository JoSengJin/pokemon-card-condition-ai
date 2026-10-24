import json
from pathlib import Path
import tempfile
import unittest

import torch

from test_pipeline import fixture
from card_condition.model import ConditionModel
from card_condition.side_experiment import experiment, side_rows, side_views


class FineTuneLastTest(unittest.TestCase):
    def test_only_last_block_trains_and_selected_checkpoint_matches_report(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, records = fixture(root)
            for row in records:
                row['side_annotations'] = {side: {'image': str(root / row[side]), 'box': [0, 0, 1, 1],
                                                   'labels': dict(row['labels'])} for side in ('front', 'back')}
            manifest.write_text(''.join(json.dumps(row) + '\n' for row in records))
            torch.manual_seed(42)
            initial = ConditionModel(pretrained=False).features.state_dict()
            output = root / 'fine-tuned'
            report = experiment(manifest, output, device='cpu', epochs=2, pretrained=False, fine_tune_last=True)
            meta = torch.load(output / 'model.pt', weights_only=True)
            self.assertTrue(meta['fine_tune_last'])
            self.assertTrue(all(torch.equal(value, meta['backbone'][key]) for key, value in initial.items()
                                if not key.startswith('12.')))
            self.assertTrue(any(not torch.equal(value, meta['backbone'][key]) for key, value in initial.items()
                                if key.startswith('12.') and value.is_floating_point()))
            backbone = ConditionModel().features.eval()
            backbone.load_state_dict(meta['backbone'])
            head = torch.nn.Linear(576, 5).eval()
            head.load_state_dict(meta['head'])
            row = next(r for r in side_rows(manifest, splits={'val'})[0] if r['id'] == report['predictions'][0]['id'])
            with torch.inference_mode():
                values = head(backbone(side_views(row['image'], row['box'])).mean((2, 3)).flatten().unsqueeze(0)).sigmoid()[0]
            self.assertTrue(torch.allclose(values, torch.tensor(list(report['predictions'][0]['probabilities'].values())), atol=1e-6))
