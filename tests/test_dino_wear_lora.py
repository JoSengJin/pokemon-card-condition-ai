import unittest
import torch
from torch import nn
from card_condition.dino_wear_lora import LowRankQKV

class WearLoRATests(unittest.TestCase):
 def test_initially_identical_then_only_adapter_trains(self):
  torch.manual_seed(4);base=nn.Linear(8,24);m=LowRankQKV(base,2);x=torch.randn(3,5,8);self.assertTrue(torch.equal(m(x),base(x)))
  before={k:v.clone() for k,v in m.base.state_dict().items()};opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=.01);loss=m(x).square().mean();loss.backward();opt.step()
  self.assertGreater(float(m.b.detach().abs().max()),0)
  for k,v in m.base.state_dict().items():self.assertTrue(torch.equal(v,before[k]))
  self.assertTrue(torch.allclose(m(x),m.merged()(x),atol=1e-6))
 def test_invalid_rank_is_rejected(self):
  for rank in (0,-1,9,True):
   with self.assertRaises(ValueError):LowRankQKV(nn.Linear(8,24),rank)

class PointTokenTests(unittest.TestCase):
 def test_portrait_padding_and_bounds(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  from card_condition.dino_wear_lora import point_token_index
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'image.png';Image.new('RGB',(300,600)).save(path)
   self.assertEqual(point_token_index(path,[0,0,1,1],{'x':.5,'y':.5}),8*16+8)
   self.assertEqual(point_token_index(path,[0,0,1,1],{'x':0,'y':.5}),8*16+4)
   with self.assertRaises(ValueError):point_token_index(path,[.2,.2,.8,.8],{'x':0,'y':.5})

 def test_odd_padding_matches_pillow_rounding(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  from card_condition.dino_wear_lora import point_token_index
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'odd.png';Image.new('RGB',(400,600)).save(path)
   self.assertEqual(point_token_index(path,[0,0,1,1],{'x':4.2/149,'y':.5}),8*16+3)

 def test_finer_grid_tracks_rendered_mark_and_retains_photo_token(self):
  import tempfile
  from pathlib import Path
  from PIL import Image,ImageDraw
  from card_condition.dino_wear_lora import point_token_index
  from card_condition.local_wear_cnn import physical_pixel_mask
  from card_condition.side_experiment import side_image
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'mark.png';im=Image.new('RGB',(300,600),'black');ImageDraw.Draw(im).rectangle((87,291,93,297),fill='red');im.save(path)
   for size in (224,448):
    token=point_token_index(path,[0,0,1,1],{'x':.3,'y':.49},image_size=size)
    mask=physical_pixel_mask(path,[0,0,1,1],halo=0,image_size=size)
    self.assertEqual(tuple(mask.shape),(size,size));grid=size//14
    valid=mask.reshape(grid,14,grid,14).any(3).any(1).flatten();self.assertTrue(valid[token])
    rendered=side_image(path,[0,0,1,1],True,size);col,row=token%grid,token//grid
    tile=rendered.crop((col*14,row*14,(col+1)*14,(row+1)*14));pixels=[tile.getpixel((i,j)) for i in range(14) for j in range(14)]
    self.assertTrue(any(r>g+10 and r>b+10 for r,g,b in pixels))
   with self.assertRaises(ValueError):point_token_index(path,[0,0,1,1],{'x':.3,'y':.49},image_size=225)
