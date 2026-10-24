import json
from pathlib import Path
import tempfile
import unittest
import torch
import test_visibility_model
from card_condition.visibility_model import experiment,VisibilityAnalyzer,TARGET,fit_side_centroids,observation_logits


class SideCentroidTest(unittest.TestCase):
    def test_side_means_use_only_corresponding_training_rows(self):
        x=torch.tensor([[0.],[2.],[10.],[14.]])
        rows=[dict(side=s,group=str(i),labels={TARGET:t}) for i,(s,t) in enumerate(
            [('front',0),('front',1),('back',0),('back',1)])]
        head=torch.nn.Linear(1,2)
        fit_side_centroids(head,x,rows)
        torch.testing.assert_close(head.weight,torch.tensor([[4.],[8.]]))
        torch.testing.assert_close(head.bias,torch.tensor([-4.,-96.]))
        values=observation_logits(head,torch.tensor([[11.],[11.]]),torch.tensor([0,1]))
        torch.testing.assert_close(values,torch.tensor([40.,-8.]))

    def test_roundtrip_side_required_and_validation_truth_independence(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            for i,row in enumerate(rows):
                if row['split']=='test':continue
                a=row['side_annotations']['back']
                a['visibility_issues']=[] if i%2 else ['glare']
                a['labels']['gradable']=1 if i%2 else 0
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before=manifest.read_bytes()
            report=experiment(manifest,root/'first',device='cpu',pretrained=False,centroid=True,side_aware=True)
            self.assertEqual(before,manifest.read_bytes())
            self.assertTrue(report['side_aware'])
            self.assertEqual({'front','back'},set(report['side_diagnostics']))
            model=VisibilityAnalyzer(root/'first/model.pt','cpu')
            with self.assertRaisesRegex(ValueError,'explicit front/back'):
                model.analyze('not-opened.png',[0,0,1,1])
            for row in report['predictions']:
                result=model.analyze(row['image'],row['box'],side=row['side'])
                self.assertAlmostEqual(row['probabilities'][TARGET],result['observation_limit_score'],places=6)
                self.assertTrue(result['requires_gemini'])
            for row in rows:
                if row['split']=='val':
                    for a in row['side_annotations'].values():
                        a['visibility_issues']=[] if a['visibility_issues'] else ['glare']
                        a['labels']['gradable']=0 if a['visibility_issues'] else 1
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            experiment(manifest,root/'changed',device='cpu',pretrained=False,centroid=True,side_aware=True)
            changed=VisibilityAnalyzer(root/'changed/model.pt','cpu')
            for key,value in model.head.state_dict().items():
                torch.testing.assert_close(value,changed.head.state_dict()[key],rtol=0,atol=0)
            meta=torch.load(root/'first/model.pt',weights_only=True)
            for key,value in [('side_aware','yes'),('preprocessing','interior90'),('head_policy','train_weighted_centroid')]:
                invalid=dict(meta);invalid[key]=value
                torch.save(invalid,root/'invalid.pt')
                with self.assertRaisesRegex(ValueError,'Unsupported'):
                    VisibilityAnalyzer(root/'invalid.pt','cpu')

    def test_missing_side_class_or_mixed_policy_refuses_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            for args in ({},{'centroid':True,'local_signals':True},{'centroid':True,'tiles':True}):
                with self.assertRaisesRegex(ValueError,'Side-aware centroids require'):
                    experiment('missing.jsonl',root/'out',side_aware=True,**args)
            manifest,_=test_visibility_model.VisibilityModelTest().setup_data(root)
            with self.assertRaisesRegex(ValueError,'Both observation'):
                experiment(manifest,root/'out',device='cpu',pretrained=False,centroid=True,side_aware=True)
            self.assertFalse((root/'out').exists())
