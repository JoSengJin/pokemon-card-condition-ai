import unittest
from unittest.mock import patch

import torch

from card_condition.model import checked_sigmoid
from card_condition.region_model import RegionAnalyzer
from card_condition.visibility_model import VisibilityAnalyzer


class FiniteLogitsTest(unittest.TestCase):
    def test_nonfinite_rejected_and_finite_outputs_unchanged(self):
        for value in (float('inf'),float('-inf'),float('nan')):
            logits=torch.tensor([[0.,value]])
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'Non-finite model logits'):
                checked_sigmoid(logits)
        logits=torch.tensor([[-1000.,-3.,0.,3.,1000.]])
        torch.testing.assert_close(checked_sigmoid(logits),logits.sigmoid(),rtol=0,atol=0)

    def test_region_rejects_bad_head_before_null_mask_or_probability(self):
        analyzer=RegionAnalyzer.__new__(RegionAnalyzer)
        analyzer.device=torch.device('cpu');analyzer.policy=False;analyzer.image_size=224
        analyzer.backbone=torch.nn.Identity().eval();analyzer.head=torch.nn.Linear(2,3).eval()
        with torch.no_grad():analyzer.head.weight.zero_()
        for batch,features in ((False,'patch_features'),(True,'batched_patch_features')):
            for value in (float('inf'),float('-inf'),float('nan')):
                with torch.no_grad():analyzer.head.bias.fill_(value)
                with self.subTest(batch=batch,value=value),patch('card_condition.region_model.'+features,return_value=torch.zeros(1,2)):
                    with self.assertRaisesRegex(ValueError,'Non-finite model logits'):
                        analyzer.analyze('not-opened.png',[0,0,1,1],'upper_left',unknown_labels=['surface_defect'],batch_views=batch)

    def test_observation_rejects_bad_head_instead_of_clear_or_limited(self):
        analyzer=VisibilityAnalyzer.__new__(VisibilityAnalyzer)
        analyzer.device=torch.device('cpu');analyzer.side_aware=True;analyzer.policy='context'
        analyzer.supported_sides=None
        analyzer.interior=False;analyzer.local_signals=False;analyzer.scaling=None
        analyzer.backbone=torch.nn.Identity().eval();analyzer.head=torch.nn.Linear(2,2).eval()
        with torch.no_grad():analyzer.head.weight.zero_()
        for side in ('front','back'):
            for value in (float('inf'),float('-inf'),float('nan')):
                with torch.no_grad():analyzer.head.bias.fill_(value)
                with self.subTest(side=side,value=value),patch('card_condition.visibility_model.observation_features',return_value=torch.zeros(1,2)):
                    with self.assertRaisesRegex(ValueError,'Non-finite model logits'):
                        analyzer.analyze('not-opened.png',[0,0,1,1],side=side)

    def test_benchmark_does_not_save_success_for_infinite_logits(self):
        from pathlib import Path
        import tempfile
        from card_condition.point_benchmark import benchmark_points
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=root/'input.jsonl';checkpoint=root/'model.pt'
            manifest.write_text('fixture');checkpoint.write_bytes(b'fixture')
            head=torch.nn.Linear(2,3)
            with torch.no_grad():head.weight.zero_();head.bias.fill_(float('inf'))
            photo=root/'photo.png';photo.write_bytes(b'fixture')
            row=dict(split='val',group='one',image=str(photo))
            with patch('card_condition.point_benchmark.point_rows',return_value=([row],{})), \
                    patch('card_condition.point_benchmark.load_probe_model',return_value=({'architecture':'fixture'},torch.nn.Identity(),head,False)), \
                    patch('card_condition.point_benchmark.patch_features',return_value=torch.zeros(1,2)):
                with self.assertRaisesRegex(ValueError,'Non-finite model logits'):
                    benchmark_points(str(manifest),str(checkpoint),root/'result.json','cpu')
            self.assertFalse((root/'result.json').exists())
