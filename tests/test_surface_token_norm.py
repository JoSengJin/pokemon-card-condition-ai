import importlib.util,unittest
from pathlib import Path
import torch
P=Path(__file__).resolve().parents[1]/'tools/experiments/surface-token-norm-20261028/transform.py'
spec=importlib.util.spec_from_file_location('token_direction',P);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


class TokenDirectionTests(unittest.TestCase):
    def test_direction_scale_padding_and_row_independence(self):
        x=torch.arange(1,2*3*384+1,dtype=torch.float64).reshape(2,3,384);mask=torch.tensor([[True,True,False],[True,False,True]]);raw=x.clone();got=mod.direction_features(x,mask)
        torch.testing.assert_close(x,raw);torch.testing.assert_close(got[~mask],x[~mask]);torch.testing.assert_close(got[mask].norm(dim=-1),torch.full((4,),384**.5,dtype=x.dtype))
        torch.testing.assert_close(got[mask]/got[mask].norm(dim=-1,keepdim=True),x[mask]/x[mask].norm(dim=-1,keepdim=True))
        scaled=x*torch.tensor([[2.,3.,4.],[5.,6.,7.]])[:,:,None];torch.testing.assert_close(mod.direction_features(scaled,mask)[mask],got[mask]);torch.testing.assert_close(mod.direction_features(x[:1],mask[:1]),got[:1])

    def test_invalid_valid_token_and_nonfinite_are_rejected(self):
        x=torch.ones(1,2,384);mask=torch.tensor([[True,False]]);x[0,0]=0
        with self.assertRaises(ValueError):mod.direction_features(x,mask)
        x.fill_(1);x[0,0,0]=float('nan')
        with self.assertRaises(ValueError):mod.direction_features(x,mask)
        with self.assertRaises(ValueError):mod.direction_features(torch.ones(1,2,383),mask)
