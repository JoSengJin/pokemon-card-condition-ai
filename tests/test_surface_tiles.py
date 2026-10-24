import json
from pathlib import Path
import tempfile
import unittest
import torch
from test_pipeline import fixture
from card_condition.region_experiment import experiment
from card_condition.region_model import RegionAnalyzer


class SurfaceTilesTest(unittest.TestCase):
    def test_surface_only_context_and_tiles_roundtrip_and_test_isolation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i,row in enumerate(rows[:4]):
                labels=dict(row['labels']);labels['surface_defect']=i%2
                a=dict(image=str(root/row['front']),box=[0,0,1,1],labels=labels,region_labels={})
                if i%2:a['defect_points']=[dict(label='surface_defect',x=.1,y=.1)]
                else:a['region_labels']={'upper_left':dict(corner_defect=None,edge_defect=None,surface_defect=0)}
                row['side_annotations']={'front':a}
            for row in rows[4:]:row['front']='unreadable-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            for policy,fine_tune in (('context',False),('tiles',False),('context',True)):
                output=root/(policy+str(fine_tune))
                report=experiment(manifest,output,epochs=2,device='cpu',pretrained=False,point_grid=True,
                    surface_input=policy,balance=True,balanced_selection=True,fine_tune_spatial=fine_tune,seed=7)
                self.assertEqual(report['seed'],7)
                self.assertEqual(torch.load(output/'model.pt',weights_only=True)['seed'],7)
                self.assertEqual(report['supported'],['surface_defect'])
                self.assertNotIn('edge_input',report)
                model=RegionAnalyzer(output/'model.pt','cpu')
                for row in report['predictions']:
                    ordinary=model.analyze(row['image'],row['card_box'],row['area'])
                    batched=model.analyze(row['image'],row['card_box'],row['area'],batch_views=True)
                    self.assertAlmostEqual(ordinary['probabilities']['surface_defect'],row['probabilities']['surface_defect'],places=5)
                    self.assertAlmostEqual(ordinary['probabilities']['surface_defect'],batched['probabilities']['surface_defect'],places=5)
                    self.assertIsNone(ordinary['probabilities']['edge_defect'])
                if policy=='tiles':
                    meta=torch.load(output/'model.pt',weights_only=True);meta['supported']=['edge_defect'];torch.save(meta,root/'bad.pt')
                    with self.assertRaisesRegex(ValueError,'surface tile'):RegionAnalyzer(root/'bad.pt','cpu')

    def test_surface_policy_does_not_mix_experiment_factors(self):
        with tempfile.TemporaryDirectory() as folder:
            for extra in ({'surface_input':'context','seed':True},{'surface_input':'context','seed':-1},{'surface_input':'views'},{'surface_input':'tiles','edge_input':'tiles'},
                          {'surface_input':'tiles','backbone_name':'resnet18','fine_tune_spatial':True},
                          {'surface_input':'tiles','nonlinear_head':True},
                          {'surface_input':'tiles','side_balance':True}):
                with self.assertRaises(ValueError):experiment('not-read',Path(folder)/'run',point_grid=True,**extra)

    def test_surface_tiles_final_evaluation_keeps_point_labels_and_leakage_guards(self):
        from card_condition.region_evaluation import evaluate_regions
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();_,rows=fixture(root)
            for i,row in enumerate(rows):
                row['labels']['surface_defect']=i%2
                a=dict(image=str(root/row['front']),box=[0,0,1,1],labels=dict(row['labels']),region_labels={})
                if i%2:a['defect_points']=[dict(label='surface_defect',x=.1,y=.1)]
                else:a['region_labels']={'upper_left':dict(corner_defect=None,edge_defect=None,surface_defect=0)}
                row['side_annotations']={'front':a}
            dev=root/'dev.jsonl';dev.write_text('\n'.join(json.dumps(r) for r in rows[:4]))
            test=root/'test.jsonl';test.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            experiment(dev,root/'model',epochs=1,device='cpu',pretrained=False,point_grid=True,surface_input='tiles')
            result=evaluate_regions(test,root/'model/model.pt',root/'result.json',[dev],'cpu')
            self.assertEqual(result['evaluation_kind'],'point_final')
            self.assertEqual(sum(result['metrics']['surface_defect'].values()),2)
            self.assertTrue(any(p['source']=='human_point' for p in result['predictions']))
            rows[4]['group']=rows[0]['group'];test.write_text(json.dumps(rows[4]))
            with self.assertRaisesRegex(ValueError,'Development'):
                evaluate_regions(test,root/'model/model.pt',root/'leaked.json',[dev],'cpu')
