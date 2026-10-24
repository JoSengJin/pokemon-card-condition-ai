import json
from pathlib import Path
import tempfile
import unittest
import torch
from test_pipeline import fixture
from card_condition.side_experiment import experiment

class EpochSelectionTest(unittest.TestCase):
    def test_checkpoint_matches_selected_epoch(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();path,rows=fixture(root)
            for r in rows:
                r['side_annotations']={s:{'image':str(root/r[s]),'box':[0,0,1,1],'labels':dict(r['labels'])} for s in ('front','back')}
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            report=experiment(path,root/'long',epochs=30,pretrained=False,device='cpu',balance=True)
            best=min(report['history'],key=lambda h:h['val'])
            self.assertEqual(best['epoch'],report['selected_epoch'])
            self.assertEqual(best['val'],report['best_validation_loss'])
            selected=experiment(path,root/'selected',epochs=best['epoch'],pretrained=False,device='cpu',balance=True)
            self.assertEqual(report['predictions'],selected['predictions'])
            self.assertEqual(report['training_metrics'],selected['training_metrics'])
            a=torch.load(root/'long/model.pt',weights_only=True)
            b=torch.load(root/'selected/model.pt',weights_only=True)
            self.assertEqual(best['epoch'],a['selected_epoch'])
            self.assertTrue(all(torch.equal(a['head'][k],b['head'][k]) for k in a['head']))
