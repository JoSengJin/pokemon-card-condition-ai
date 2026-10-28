import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
import torch
spec=importlib.util.spec_from_file_location('surface_layer8',Path(__file__).resolve().parents[1]/'tools/experiments/surface-preserved-heads-20261028/worker-layer8.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SurfaceLayer8Tests(unittest.TestCase):
    def test_selected_layers_are_aligned_normalized_and_ordered(self):
        body=Mock();a=torch.full((1,256,384),8.);b=torch.full_like(a,12.);body.get_intermediate_layers.return_value=(a,b);tensor=torch.zeros(1,3,224,224)
        mid,final=m.layer_pair(body,tensor);self.assertTrue(torch.equal(a,mid));self.assertTrue(torch.equal(b,final));body.get_intermediate_layers.assert_called_once_with(tensor,n=[7,11],reshape=False,return_class_token=False,norm=True)

    def test_incompatible_or_nonfinite_layer_outputs_stop(self):
        body=Mock()
        for values in [(torch.ones(1,256,384),),(torch.ones(1,256,384),torch.ones(1,128,384)),(torch.full((1,256,384),float('nan')),torch.ones(1,256,384))]:
            body.get_intermediate_layers.return_value=values
            with self.assertRaises(ValueError):m.layer_pair(body,torch.zeros(1,3,224,224))
