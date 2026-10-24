import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from card_condition.observation_audit import pixel_signals,spatial_signals,audit_inputs
import test_visibility_model


class ObservationAuditTest(unittest.TestCase):
    def test_uniform_and_localized_signal_without_region_truth(self):
        white=pixel_signals(Image.new('RGB',(9,9),'white'))
        self.assertEqual(1.,white['bright_fraction'])
        self.assertEqual(0.,white['gradient_energy'])
        image=Image.new('RGB',(9,9),'black')
        image.paste('white',(0,0,3,3))
        result=spatial_signals(image)
        self.assertEqual(9,len(result['cells']))
        self.assertEqual(255,result['signals']['cell_luminance_spread'])
        self.assertNotIn('labels',result['cells'][0])
        self.assertEqual(1,spatial_signals(Image.new('RGB',(1,1)))['grid_size'])

    def test_audit_never_opens_val_or_test_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            for row in rows:
                if row['split']!='train':
                    row['front']=row['back']='must-not-open.png'
                    row['side_annotations']='must-not-validate'
            rows.append(dict(split='test',front='also-missing.png'))
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before=manifest.read_bytes()
            report=audit_inputs(manifest,root/'audit')
            self.assertEqual(2,report['faces'])
            self.assertEqual(before,manifest.read_bytes())
            self.assertTrue(all(r['split']=='train' for r in report['rows']))
            self.assertEqual(0,report['actual_calls_saved'])
            self.assertFalse(report['labels_modified'])
            self.assertTrue((root/'audit/index.html').exists())
            self.assertEqual(report,json.loads((root/'audit/report.json').read_text()))
            with self.assertRaisesRegex(ValueError,'Output exists'):
                audit_inputs(manifest,root/'audit')
