import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import torch

from test_pipeline import fixture
from card_condition.side_experiment import experiment
from card_condition.side_evaluation import evaluate_sides

class SideEvaluationTest(unittest.TestCase):
    def test_regression_and_final_history_guards(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for r in rows:
                for side in ('front','back'): r[side]=str(root/r[side])
                r['side_annotations']={s:{'image':r[s],'box':[0,0,1,1],'labels':dict(r['labels'])} for s in ('front','back')}
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            experiment(manifest,root/'model',epochs=1,device='cpu',pretrained=False,tiles=True)
            model=root/'model/model.pt'
            regression=evaluate_sides(manifest,model,root/'regression.json','regression',device='cpu')
            self.assertEqual(2,regression['n_cards'])
            self.assertEqual('human box + four overlapping tiles',regression['preprocessing'])
            with self.assertRaisesRegex(ValueError,'history'):
                evaluate_sides(manifest,model,root/'no-history.json','final',device='cpu')
            # Relabeling an old test as final cannot conceal its development history.
            candidate=root/'final.jsonl';candidate.write_text(json.dumps(rows[4])+'\n')
            with self.assertRaisesRegex(ValueError,'개발에 사용'):
                evaluate_sides(candidate,model,root/'blocked.json','final',[manifest],device='cpu')
            old=dict(rows[4],id='renamed',group='renamed')
            candidate.write_text(json.dumps(old)+'\n')
            with self.assertRaisesRegex(ValueError,'개발에 사용'):
                evaluate_sides(candidate,model,root/'blocked.json','final',[manifest],device='cpu')
            # A truly new fixture passes; this proves mechanics, not real-world quality.
            fresh=dict(rows[4],id='new',group='new')
            fresh['side_annotations']={}
            for side,color in [('front','yellow'),('back','purple')]:
                p=root/(side+'-new.png');Image.new('RGB',(100,140),color).save(p)
                fresh[side]=str(p);fresh['side_annotations'][side]={'image':str(p),'box':[0,0,1,1],'labels':dict(fresh['labels'])}
            candidate.write_text(json.dumps(fresh)+'\n')
            result=evaluate_sides(candidate,model,root/'final.json','final',[manifest],device='cpu')
            self.assertEqual('final',result['evaluation_kind'])
            self.assertFalse(result['production_ready'])
            self.assertTrue(result['requires_gemini'])
            self.assertEqual(1,len(result['history']))
            with self.assertRaisesRegex(ValueError,'exists'):
                evaluate_sides(candidate,model,root/'final.json','final',[manifest],device='cpu')
            # Training group rejection also applies to regression.
            contaminated=dict(rows[0],split='test');candidate.write_text(json.dumps(contaminated)+'\n')
            with self.assertRaisesRegex(ValueError,'개발에 사용'):
                evaluate_sides(candidate,model,root/'bad-regression.json','regression',device='cpu')

    def test_no_supported_truth_is_not_a_successful_evaluation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();_,rows=fixture(root)
            for row in rows:
                row['side_annotations']={side:dict(image=str(root/row[side]),box=[0,0,1,1],
                    labels=dict(row['labels'])) for side in ('front','back')}
            history=root/'history.jsonl'
            history.write_text('\n'.join(json.dumps(r) for r in rows[:4]))
            experiment(history,root/'trained',epochs=1,device='cpu',pretrained=False,crop=True)
            checkpoint=root/'trained/model.pt'
            meta=torch.load(checkpoint,weights_only=True)
            # A valid checkpoint may expose only a subset of its trained outputs.
            meta['supported']=['corner_defect'];torch.save(meta,checkpoint)
            for row in rows[4:]:
                for annotation in row['side_annotations'].values():
                    annotation['labels']['corner_defect']=None
            candidate=root/'test.jsonl'
            candidate.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            for kind in ('final','regression'):
                output=root/(kind+'.json')
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'No scored supported'):
                    evaluate_sides(candidate,checkpoint,output,kind,[history],device='cpu')
                self.assertFalse(output.exists())
            # One explicit known answer is enough to report its true denominator.
            rows[4]['side_annotations']['front']['labels']['corner_defect']=0
            candidate.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            report=evaluate_sides(candidate,checkpoint,root/'known.json','final',[history],device='cpu')
            self.assertEqual(1,report['rates_at_05']['corner_defect']['scored'])
            self.assertEqual(1,report['rates_at_05']['corner_defect']['negative'])
            self.assertEqual(0,report['rates_at_05']['corner_defect']['positive'])
            self.assertIsNone(report['rates_at_05']['corner_defect']['false_negative_rate'])
            self.assertEqual(0,report['actual_calls_saved'])
