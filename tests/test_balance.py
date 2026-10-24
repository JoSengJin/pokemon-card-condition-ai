import json
from pathlib import Path
import tempfile
import unittest
import torch
from test_pipeline import fixture
from card_condition.data import LABELS
from card_condition.side_experiment import experiment, training_balance

class BalanceTest(unittest.TestCase):
    def test_weights_use_only_known_training_labels(self):
        rows=[{'split':'train','labels':dict.fromkeys(LABELS,v)} for v in (1,0,0,None)]
        rows += [{'split':'val','labels':{}},{'split':'test','labels':{}}]
        counts,weights=training_balance(rows,LABELS)
        self.assertEqual([2.0]*5,weights)
        self.assertEqual({'positive':1,'negative':2,'unknown':1},counts[LABELS[0]])
        self.assertEqual([1.0]*5,training_balance(rows,[])[1])

    def test_balanced_training_and_test_isolation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();path,rows=fixture(root)
            for r in rows:
                r['side_annotations']={s:{'image':str(root/r[s]),'box':[0,0,1,1],'labels':dict(r['labels'])} for s in ('front','back')}
            rows[0]['side_annotations']['front']['labels']['edge_defect']=None
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            first=experiment(path,root/'a',epochs=1,pretrained=False,device='cpu',balance=True)
            for r in rows:
                if r['split']=='test':r['front']='missing';r['labels']={}
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            second=experiment(path,root/'b',epochs=1,pretrained=False,device='cpu',balance=True)
            self.assertEqual(first['history'],second['history'])
            self.assertEqual(first['predictions'],second['predictions'])
            self.assertEqual(1,first['train_label_counts']['edge_defect']['unknown'])
            self.assertTrue(first['balance'])
            self.assertEqual('unweighted validation BCE',first['selection_metric'])
            meta=torch.load(root/'a/model.pt',weights_only=True)
            self.assertEqual(first['positive_weights'],meta['positive_weights'])
            self.assertTrue(torch.isfinite(meta['head']['weight']).all())
