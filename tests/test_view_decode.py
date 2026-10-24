"""Pixel parity and request-scoped decode reuse, independent of learned weights."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps
import torch
from torchvision.transforms.functional import to_tensor, normalize

from card_condition.side_experiment import side_tensor, view_tensors
from card_condition.edge_views import patch_features, batched_patch_features, tile_prefix_maps


class ViewDecodeTest(unittest.TestCase):
    def test_pixels_exif_decode_count_and_fresh_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'image.jpg'
            image = Image.effect_noise((137,191),50)
            exif = Image.Exif(); exif[274] = 6
            image.save(path, exif=exif)
            boxes = [[0,0,1,1], [.013,.029,.51,.62], [.5,.5,1,1]]
            for size in (224,448):
                expected = []
                for box in boxes:
                    # Reference mapping before decode reuse, including EXIF and RGB.
                    with Image.open(path) as source:
                        rgb = ImageOps.exif_transpose(source).convert('RGB')
                        w,h = rgb.size
                        crop = rgb.crop((math.floor(box[0]*w),math.floor(box[1]*h),
                                         math.ceil(box[2]*w),math.ceil(box[3]*h)))
                        view = ImageOps.pad(crop,(size,size),method=Image.Resampling.BILINEAR,color=(128,128,128))
                        expected.append(normalize(to_tensor(view),[.485,.456,.406],[.229,.224,.225]))
                with patch('PIL.Image.open', wraps=Image.open) as opened:
                    actual = list(view_tensors(path,boxes,size))
                    self.assertEqual(1,opened.call_count)
                for box,old,new in zip(boxes,expected,actual):
                    torch.testing.assert_close(new,old,rtol=0,atol=0)
                    torch.testing.assert_close(side_tensor(path,box,True,size),old,rtol=0,atol=0)
            old = actual[0]
            Image.new('RGB',(137,191),'red').save(path)
            self.assertFalse(torch.equal(old,next(view_tensors(path,boxes,448))))
            row = dict(image=str(path),box=[0,0,1,1],card_box=[0,0,1,1],area='upper_left')
            backbone = torch.nn.Identity().eval()
            for function in (patch_features,batched_patch_features):
                for policy in (False, True, 'tiles', 'tiles-max'):
                    with torch.inference_mode(), patch('PIL.Image.open',wraps=Image.open) as opened:
                        function(backbone,row,'cpu',policy)
                        self.assertEqual(1,opened.call_count)
            with patch('PIL.Image.open',wraps=Image.open) as opened:
                maps = tile_prefix_maps(backbone,row,'cpu')
                self.assertEqual(1,opened.call_count)
            reference = torch.stack(list(view_tensors(path,[row['box'],[0,0,.5,.5],[.5,0,1,.5],[0,.5,.5,1],[.5,.5,1,1]]))).unsqueeze(0)
            torch.testing.assert_close(maps,reference,rtol=0,atol=0)
            with self.assertRaises(ValueError):
                list(view_tensors(path,boxes,123))
