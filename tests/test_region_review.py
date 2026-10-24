import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from card_condition.region_review import write_region_review

class NativeRegionReviewTest(unittest.TestCase):
    def test_native_pixels_and_one_to_one_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';image=Image.new('RGB',(100,80),(12,34,56));image.putpixel((20,20),(255,0,0));image.save(source)
            out=root/'review';r=write_region_review(source,[.2,.25,.4,.5],out)
            actual=Image.open(out/'native.png');self.assertEqual(actual.size,(20,20));self.assertEqual(actual.tobytes(),image.crop((20,20,40,40)).tobytes())
            self.assertEqual(r['default_display_scale'],1);self.assertEqual(r['labels_created'],0);self.assertIsNone(r['quality_decision'])
            self.assertIn('width="20" height="20"',(out/'index.html').read_text())
            self.assertEqual(json.loads((out/'evidence.json').read_text())['pixel_box'],[20,20,40,40])
            with self.assertRaises(FileExistsError):write_region_review(source,[.2,.25,.4,.5],out)

    def test_exif_oriented_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.jpg';image=Image.new('RGB',(30,50));exif=Image.Exif();exif[274]=6;image.save(source,exif=exif)
            r=write_region_review(source,[0,0,1,1],root/'review')
            self.assertEqual(r['oriented_source_size'],[50,30]);self.assertEqual(r['native_crop_size'],[50,30])

    def test_bad_boxes_create_no_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';Image.new('RGB',(10,10)).save(source)
            for box in [[0,0,0,1],[-.1,0,1,1],[0,0,float('nan'),1],[False,0,1,1],[0,0,1]]:
                with self.assertRaises(ValueError):write_region_review(source,box,root/'bad')
                self.assertFalse((root/'bad').exists())

    def test_context_marker_matches_crop_without_changing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';image=Image.new('RGB',(100,80),(12,34,56));image.save(source)
            out=root/'review';r=write_region_review(source,[.2,.25,.4,.5],out)
            self.assertEqual(Image.open(out/'source.png').tobytes(),image.tobytes())
            self.assertEqual(Image.open(out/'context.png').getpixel((20,20)),(255,138,0))
            self.assertEqual(Image.open(out/'context.png').getpixel((0,0)),(12,34,56))
            self.assertEqual(Image.open(out/'native.png').tobytes(),image.crop((20,20,40,40)).tobytes())
            self.assertFalse(r['marker_is_condition_prediction'])
            self.assertIn('src="context.png"',(out/'index.html').read_text())
