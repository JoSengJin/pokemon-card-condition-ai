"""Two audit passes must observe the same decoded photos, without reading test data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from test_pipeline import fixture
from card_condition.data_coverage import coverage_report, data_coverage
from card_condition.point_dataset import point_rows


class CoveragePhotoConsistencyTest(unittest.TestCase):
    def prepare(self, root, with_point):
        manifest,records=fixture(root)
        record=records[1]
        annotation=dict(image=str(root/record['front']),box=[0,0,1,1],
                        labels=dict(record['labels']),visibility_issues=[])
        if with_point:
            annotation['defect_points']=[dict(label='edge_defect',x=.1,y=.1)]
        record['side_annotations']={'front':annotation}
        for final in records[4:]:
            final['front']='missing-final.png'
            final['labels']='sealed final labels'
            final['side_annotations']='sealed final annotation'
        manifest.write_text('\n'.join(json.dumps(r) for r in records))
        return manifest,root/record['front']

    def test_changed_photo_between_passes_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,photo=self.prepare(root,with_point=True)
            manifest_before=manifest.read_bytes();output=root/'audit.json'
            def changed(*args,**kwargs):
                Image.new('RGB',(90,130),(12,34,56)).save(photo)
                return point_rows(*args,**kwargs)
            with patch('card_condition.data_coverage.point_rows',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'photos changed'):
                    data_coverage(manifest,output)
            self.assertFalse(output.exists())
            self.assertEqual(manifest_before,manifest.read_bytes())

    def test_photo_without_region_patch_is_also_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,photo=self.prepare(root,with_point=False)
            self.assertEqual([],point_rows(manifest,grid=True)[0])
            def changed(*args,**kwargs):
                Image.new('RGB',(90,130),(12,34,56)).save(photo)
                return point_rows(*args,**kwargs)
            with patch('card_condition.data_coverage.point_rows',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'photos changed'):
                    coverage_report(manifest)

    def test_changed_encoding_with_identical_pixels_keeps_audit_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,photo=self.prepare(root,with_point=True)
            baseline=coverage_report(manifest)
            original_hash=hashlib.sha256(photo.read_bytes()).hexdigest()
            def reencoded(*args,**kwargs):
                with Image.open(photo) as source:
                    pixels=source.copy()
                info=PngImagePlugin.PngInfo();info.add_text('audit','same decoded pixels')
                pixels.save(photo,pnginfo=info)
                return point_rows(*args,**kwargs)
            with patch('card_condition.data_coverage.point_rows',side_effect=reencoded):
                result=coverage_report(manifest)
            self.assertNotEqual(original_hash,hashlib.sha256(photo.read_bytes()).hexdigest())
            self.assertEqual(baseline,result)


if __name__ == '__main__':
    unittest.main()
