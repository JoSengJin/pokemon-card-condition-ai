import json
from pathlib import Path
import tempfile
import unittest

import torch

from test_pipeline import fixture
from card_condition.side_experiment import experiment, side_rows
from card_condition.side_model import SideAnalyzer
from card_condition.side_evaluation import evaluate_sides
from card_condition.comparison import compare_validation
from card_condition.benchmark import benchmark_validation


class SideModelTest(unittest.TestCase):
    def test_both_backbones_restore_and_comparison_guards(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for row in rows:
                row['side_annotations']={side:{'image':str(root/row[side]),'box':[0,0,1,1],
                                               'labels':dict(row['labels'])} for side in ('front','back')}
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            reports=[]
            for name,crop in (('mobilenet_v3_small',False),('resnet18',True)):
                output=root/name
                report=experiment(manifest,output,device='cpu',epochs=1,pretrained=False,
                                  crop=crop,backbone_name=name)
                analyzer=SideAnalyzer(output/'model.pt','cpu')
                row=side_rows(manifest,splits={'val'})[0][0]
                actual=analyzer.predict(row['image'],row['box'])
                self.assertTrue(all(abs(actual[k]-report['predictions'][0]['probabilities'][k])<1e-6 for k in actual))
                result=analyzer.analyze(front=row['image'],front_box=row['box'])
                self.assertEqual(['back'],result['missing_sides'])
                self.assertIsNone(result['sides']['back'])
                self.assertTrue(result['requires_gemini'])
                with self.assertRaisesRegex(ValueError,'At least'): analyzer.analyze()
                with self.assertRaisesRegex(ValueError,'Card box'): analyzer.predict(row['image'],[0,0,0,1])
                if crop:
                    with self.assertRaisesRegex(ValueError,'human-verified'): analyzer.predict(row['image'])
                # Old MobileNet metadata continues to load without a backbone_name.
                meta=torch.load(output/'model.pt',weights_only=True)
                if name=='mobilenet_v3_small': del meta['backbone_name']
                meta['supported']=meta['supported'][:-1]
                torch.save(meta,root/(name+'-subset.pt'))
                self.assertIsNone(SideAnalyzer(root/(name+'-subset.pt'),'cpu').predict(row['image'],row['box'])['surface_defect'])
                evaluate_sides(manifest,output/'model.pt',root/(name+'-regression.json'),'regression',device='cpu')
                timing=benchmark_validation(manifest,output/'model.pt',root/(name+'-speed.json'),'cpu')
                self.assertEqual(12,timing['samples'])
                self.assertEqual(4,timing['n_sides'])
                self.assertGreaterEqual(timing['p95_seconds'],timing['median_seconds'])
                with self.assertRaisesRegex(ValueError,'exists'):
                    benchmark_validation(manifest,output/'model.pt',root/(name+'-speed.json'),'cpu')
                reports.append(output/'report.json')
            compared=compare_validation(manifest,reports,root/'compare.json')
            self.assertEqual(2,len(compared['models']))
            self.assertFalse(compared['production_ready'])
            self.assertEqual(0,compared['actual_calls_saved'])
            changed=json.loads(reports[-1].read_text());changed['evaluation_kind']='final'
            reports[-1].write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'same snapshot'):
                compare_validation(manifest,reports,root/'invalid.json')
            changed['evaluation_kind']='validation';changed['metrics']['gradable']['fp']+=1
            reports[-1].write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'metrics'):
                compare_validation(manifest,reports,root/'invalid.json')

    def test_resnet_last_block_is_not_silently_enabled(self):
        with self.assertRaisesRegex(ValueError,'MobileNet'):
            experiment('unused','unused',fine_tune_last=True,backbone_name='resnet18')

    def test_malformed_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invalid.pt'
            for payload in ([], {'backbone_name': 7}, {'architecture':'resnet18_single_side_v1'}):
                torch.save(payload,path)
                with self.assertRaisesRegex(ValueError,'Unsupported'):
                    SideAnalyzer(path,'cpu')
