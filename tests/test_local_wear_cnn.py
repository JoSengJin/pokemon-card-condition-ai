import unittest
import torch
from card_condition.local_wear_cnn import LocalWearCNN,sparse_wear_loss
class LocalWearTests(unittest.TestCase):
 def test_no_downsampling_and_small_capacity(self):
  model=LocalWearCNN();self.assertEqual(tuple(model(torch.zeros(2,3,32,48)).shape),(2,1,32,48));self.assertEqual(sum(p.numel() for p in model.parameters()),817)
 def test_unknown_pixels_on_positive_are_not_negative_labels(self):
  a=torch.zeros(8,8);b=a.clone();b[7,7]=100
  self.assertEqual(float(sparse_wear_loss(a,1,(2,2))),float(sparse_wear_loss(b,1,(2,2))))
 def test_normal_loss_targets_worst_false_alarm(self):
  a=torch.full((8,8),-5.);b=a.clone();b[7,7]=5
  self.assertGreater(float(sparse_wear_loss(b,0)),float(sparse_wear_loss(a,0)))
 def test_missing_truth_rejected(self):
  for target,point in [(None,None),(1,None),(1,(100,100))]:
   with self.assertRaises(ValueError):sparse_wear_loss(torch.zeros(8,8),target,point)

 def test_padding_peak_is_not_damage(self):
  logits=torch.full((8,8),-5.);logits[0,0]=100
  valid=torch.zeros((8,8),dtype=torch.bool);valid[2:6,2:6]=True
  self.assertLess(float(sparse_wear_loss(logits,0,valid_mask=valid)),.01)
  with self.assertRaises(ValueError):sparse_wear_loss(logits,1,(0,0),valid)

 def test_physical_mask_matches_letterboxed_photo_and_halo(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  from card_condition.local_wear_cnn import physical_pixel_mask
  with tempfile.TemporaryDirectory() as folder:
   photo=Path(folder)/'normal.png';Image.new('RGB',(200,100)).save(photo)
   mask=physical_pixel_mask(photo,[0,0,1,1])
  expected=torch.zeros((224,224),dtype=torch.bool);expected[58:166,2:222]=True
  self.assertTrue(torch.equal(mask,expected))

 def test_dilation_increases_context_without_downsampling_or_extra_parameters(self):
  a,b=LocalWearCNN(),LocalWearCNN(dilation=2)
  for model in (a,b):
   for module in model:
    if isinstance(module,torch.nn.Conv2d):torch.nn.init.ones_(module.weight);torch.nn.init.zeros_(module.bias)
  x=torch.zeros(1,3,15,15);x[0,0,7,7]=1
  self.assertEqual(a(x)[0,0,7,10].item(),0)
  self.assertGreater(b(x)[0,0,7,10].item(),0)
  self.assertEqual(sum(p.numel() for p in b.parameters()),817)
  self.assertEqual(a(x).shape,b(x).shape)
  with self.assertRaises(ValueError):LocalWearCNN(dilation=0)

 def test_click_uncertainty_follows_native_resolution(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  from card_condition.local_wear_cnn import native_click_radius
  with tempfile.TemporaryDirectory() as folder:
   photo=Path(folder)/'micro.png';Image.new('RGB',(100,50)).save(photo)
   radius=native_click_radius(photo,[0,0,1,1])
  self.assertEqual(radius,3)
  z=torch.full((12,12),-5.);z[5,7]=5
  self.assertLess(float(sparse_wear_loss(z,1,(5,5),radius=radius)),.01)
  self.assertGreater(float(sparse_wear_loss(z,1,(5,5))),4)
  z[11,11]=100
  self.assertLess(float(sparse_wear_loss(z,1,(5,5),radius=radius)),.01)

 def test_leaky_activation_keeps_negative_feature_gradients_alive(self):
  gradients=[]
  for leaky in (False,True):
   model=LocalWearCNN(leaky=leaky)
   for module in model:
    if isinstance(module,torch.nn.Conv2d):torch.nn.init.ones_(module.weight);torch.nn.init.zeros_(module.bias)
   loss=sparse_wear_loss(model(-torch.ones(1,3,15,15))[0,0],1,(7,7));loss.backward()
   gradients.append(float(model[0].weight.grad.abs().sum()))
   self.assertEqual(sum(p.numel() for p in model.parameters()),817)
  self.assertEqual(gradients[0],0)
  self.assertGreater(gradients[1],0)
