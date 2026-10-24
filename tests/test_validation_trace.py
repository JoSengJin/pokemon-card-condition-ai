import unittest
import torch
from card_condition.region_experiment import validation_diagnostics


class ValidationTraceTest(unittest.TestCase):
    def test_weighted_objective_and_unknowns_without_gradients(self):
        logits=torch.tensor([[1.,2.,3.],[0.,-1.,1.],[-2.,1.,0.]],requires_grad=True)
        truth=torch.tensor([[-1.,0.,-1.],[-1.,1.,-1.],[-1.,-1.,-1.]])
        weights=torch.tensor([[0.,.5,0.],[0.,1.,0.],[0.,0.,0.]])
        result=validation_diagnostics(logits,truth,weights,['edge_defect'])
        self.assertEqual({'edge_defect'},set(result))
        value=result['edge_defect']
        self.assertEqual(dict(tp=0,tn=0,fp=1,fn=1),value['metrics_at_05'])
        normal,defect=value['classes']['normal'],value['classes']['defect']
        self.assertEqual(.5,normal['effective_mass'])
        self.assertEqual(1.,defect['effective_mass'])
        self.assertEqual(1,normal['known'])
        expected=torch.nn.functional.binary_cross_entropy_with_logits(logits[:2,1],truth[:2,1],reduction='none')
        self.assertAlmostEqual(float((expected.detach()*weights[:2,1]).sum()/1.5),
            (normal['weighted_bce']*.5+defect['weighted_bce'])/1.5,places=6)
        self.assertIsNone(logits.grad)
        result=validation_diagnostics(logits,torch.full_like(truth,-1),weights,['edge_defect'])
        self.assertIsNone(result['edge_defect']['classes']['normal']['weighted_bce'])

    def test_class_group_weights_ignore_train_and_repeated_patches(self):
        from card_condition.region_experiment import class_group_validation_weights
        rows=[dict(split='val',group='a',labels=dict(corner_defect=None,edge_defect=0,surface_defect=None)) for _ in range(3)]
        rows += [dict(split='val',group='b',labels=dict(corner_defect=None,edge_defect=0,surface_defect=None)),
            dict(split='val',group='c',labels=dict(corner_defect=None,edge_defect=1,surface_defect=None)),
            dict(split='train',group='train',labels=dict(corner_defect=None,edge_defect=1,surface_defect=None))]
        weights=class_group_validation_weights(rows,['edge_defect'])
        self.assertAlmostEqual(.5,sum(w[1] for w in weights[:3]))
        self.assertEqual(.5,weights[3][1])
        self.assertEqual(1.,weights[4][1])
        self.assertEqual([0.,0.,0.],weights[5])
        with self.assertRaisesRegex(ValueError,'both validation classes'):
            class_group_validation_weights(rows[:4],['edge_defect'])

    def test_selection_keeps_training_and_restores_selected_checkpoint(self):
        import json
        from pathlib import Path
        import tempfile
        from test_pipeline import fixture
        from card_condition.region_experiment import experiment
        from card_condition.point_probe import load_probe_model
        from card_condition.edge_views import patch_features
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i,row in enumerate(rows[:4]):
                row['side_annotations']={'front':dict(image=str(root/row['front']),box=[0,0,1,1],
                    labels=dict(row['labels']),region_labels={'upper_left':dict(corner_defect=None,
                    edge_defect=i%2,surface_defect=None)})}
                if i%2:
                    row['side_annotations']['front']['defect_points']=[dict(label='edge_defect',x=.02,y=.02)]
            for row in rows[4:]:row['front']='unread-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows));before=manifest.read_bytes()
            reports=[experiment(manifest,root/str(mode),epochs=3,device='cpu',pretrained=False,
                point_grid=True,balance=True,edge_input='tiles',balanced_selection=mode) for mode in (False,True)]
            self.assertEqual([h['train'] for h in reports[0]['history']],[h['train'] for h in reports[1]['history']])
            report=reports[1];self.assertTrue(report['balanced_selection'])
            self.assertEqual(min(h['val'] for h in report['history']),report['best_validation_loss'])
            meta,backbone,head,policy=load_probe_model(root/'True/model.pt')
            self.assertTrue(meta['balanced_selection'])
            for prediction in report['predictions']:
                with torch.inference_mode():score=head(patch_features(backbone,prediction,'cpu',policy)).sigmoid()[0,1].item()
                self.assertAlmostEqual(score,prediction['probabilities']['edge_defect'],places=6)
            self.assertEqual(before,manifest.read_bytes())
            with self.assertRaisesRegex(ValueError,'requires point-grid'):
                experiment(manifest,root/'invalid',balanced_selection=True)
