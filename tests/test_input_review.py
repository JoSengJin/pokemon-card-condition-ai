import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import torch
from torchvision.transforms.functional import normalize, to_tensor

from card_condition.input_review import input_review
from card_condition.side_experiment import side_tensor
from test_pipeline import fixture


class InputReviewTest(unittest.TestCase):
    def test_only_train_images_and_actual_model_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for i, r in enumerate(rows):
                if r['split'] != 'train':
                    r['front'] = 'must-not-read-val-or-test.png'
                    continue
                r['side_annotations'] = {'front': dict(image=str(root/r['front']),
                    box=[.1, .1, .9, .9], labels=r['labels'], region_labels={
                        'upper_left':dict(corner_defect=i, edge_defect=i, surface_defect=i)})}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            result = input_review(manifest, root/'review', ['0', '1'])
            self.assertEqual(2, result['patches'])
            self.assertEqual(14, len(result['samples']))
            self.assertFalse(result['labels_modified'])
            tiles=[s for s in result['samples'] if s['view'].startswith('tile-')]
            self.assertEqual(8,len(tiles))
            for tile in tiles[:4]:
                with Image.open(root/'review'/f"0-{tile['view']}-224.png") as im:
                    actual=normalize(to_tensor(im),[.485,.456,.406],[.229,.224,.225])
                self.assertTrue(torch.equal(actual,side_tensor(root/'0-front.png',tile['box'],True,224)))
            box = result['samples'][0]['box']
            for size in (224, 448):
                with Image.open(root/'review'/f'0-full-{size}.png') as im:
                    self.assertEqual((size, size), im.size)
                    actual = normalize(to_tensor(im), [.485,.456,.406], [.229,.224,.225])
                self.assertTrue(torch.equal(actual, side_tensor(root/'0-front.png', box, True, size)))
            self.assertEqual(before, manifest.read_bytes())
            with self.assertRaisesRegex(ValueError, 'exists'):
                input_review(manifest, root/'review', ['0'])
            with self.assertRaisesRegex(ValueError, 'train patches'):
                input_review(manifest, root/'wrong', ['2'])
            self.assertFalse((root/'wrong').exists())
