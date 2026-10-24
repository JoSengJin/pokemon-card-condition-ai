import unittest
import torch
import tempfile
import json
from pathlib import Path
from card_condition.feature_scaling import fit_train_scaler,fold_scaler


class FeatureScalingTest(unittest.TestCase):
    def test_validation_features_do_not_affect_fitted_scaler(self):
        values=torch.tensor([[1.,2.],[3.,6.],[100.,-100.]])
        mean,scale=fit_train_scaler(values,[.5,.5,0])
        self.assertTrue(torch.equal(mean,torch.tensor([2.,4.])))
        self.assertTrue(torch.equal(scale,torch.tensor([1.,2.])))
        values[2]=torch.tensor([float('nan'),float('inf')])
        other=fit_train_scaler(values,[.5,.5,0])
        self.assertTrue(torch.equal(mean,other[0]));self.assertTrue(torch.equal(scale,other[1]))

    def test_physical_group_mass_and_constant_dimensions(self):
        values=torch.tensor([[0.,5.],[0.,5.],[10.,5.]])
        mean,scale=fit_train_scaler(values,[.5,.5,1])
        self.assertEqual(mean.tolist(),[5.,5.])
        self.assertAlmostEqual(scale[1].item(),.001,places=6)
        self.assertTrue(torch.isfinite((values-mean)/scale).all())

    def test_folded_head_matches_scaled_logits(self):
        torch.manual_seed(1)
        values=torch.randn(10,8)
        head=torch.nn.Linear(8,3)
        mean,scale=fit_train_scaler(values,[1]*8+[0]*2)
        folded=fold_scaler(head.state_dict(),mean,scale)
        actual=torch.nn.functional.linear(values,folded['weight'],folded['bias'])
        expected=head((values-mean)/scale)
        self.assertTrue(torch.allclose(actual,expected,atol=1e-6))

    def test_invalid_or_missing_training_evidence_is_rejected(self):
        for weights in ([0,0],[1,-1],[1,float('nan')],[1]):
            with self.assertRaises(ValueError):fit_train_scaler(torch.zeros(2,3),weights)
        with self.assertRaises(ValueError):fit_train_scaler(torch.tensor([[float('nan')]]),[1])

    def test_optional_heads_roundtrip_through_existing_region_api(self):
        from test_pipeline import fixture
        from card_condition.region_experiment import experiment
        from card_condition.region_model import RegionAnalyzer
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i,row in enumerate(rows[:4]):
                a=dict(image=str(root/row['front']),box=[0,0,1,1],labels=dict(row['labels']),region_labels={})
                if i%2:a['defect_points']=[dict(label='edge_defect',x=.1,y=.1)]
                else:a['region_labels']={'upper_center':dict(corner_defect=None,edge_defect=0,surface_defect=None)}
                row['side_annotations']={'front':a}
            for row in rows[4:]:row['front']='must-not-read-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            for option in ('standardize_features','nonlinear_head','focal_loss'):
                output=root/option
                report=experiment(manifest,output,epochs=2,device='cpu',pretrained=False,point_grid=True,
                    edge_input='tiles',balance=True,balanced_selection=True,**{option:True})
                analyzer=RegionAnalyzer(output/'model.pt','cpu')
                for prediction in report['predictions']:
                    actual=analyzer.analyze(prediction['image'],prediction['card_box'],prediction['area'])
                    self.assertAlmostEqual(actual['probabilities']['edge_defect'],prediction['probabilities']['edge_defect'],places=5)
                    self.assertIsNone(actual['probabilities']['surface_defect'])

    def test_invalid_head_size_and_combined_experiment_factors_rejected(self):
        from card_condition.region_head import region_head
        from card_condition.region_experiment import experiment
        for size in (True,7,-1,'8'):
            with self.assertRaises(ValueError):region_head(4,size)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'Nonlinear head'):
                experiment('not-read',Path(folder)/'run',point_grid=True,edge_input='tiles',nonlinear_head=True,standardize_features=True)

    def test_focal_downweights_easy_examples_and_has_finite_gradient(self):
        from card_condition.region_experiment import binary_training_loss
        logits=torch.tensor([5.,-5.],requires_grad=True);truth=torch.tensor([1.,1.])
        ordinary=binary_training_loss(logits,truth)
        focused=binary_training_loss(logits,truth,True)
        self.assertLess((focused[0]/ordinary[0]).item(),.001)
        self.assertGreater((focused[1]/ordinary[1]).item(),.98)
        focused.sum().backward();self.assertTrue(torch.isfinite(logits.grad).all())
