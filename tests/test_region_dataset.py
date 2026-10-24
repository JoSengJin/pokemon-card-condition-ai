import json
from pathlib import Path
import tempfile
import unittest

from test_pipeline import fixture
from card_condition.region_dataset import region_audit, region_rows


class RegionDatasetTest(unittest.TestCase):
    def test_side_coverage_counts_physical_groups_not_patches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            for row in rows[:4]:
                labels = {'corner_defect': row['labels']['corner_defect'], 'edge_defect': None, 'surface_defect': None}
                row['side_annotations'] = {'front': {'image': str(root / row['front']),
                    'box': [0, 0, 1, 1], 'labels': dict(row['labels']),
                    'region_labels': {'upper_left': labels}}}
            rows[0]['side_annotations']['front']['region_labels']['lower_right'] = dict(
                rows[0]['side_annotations']['front']['region_labels']['upper_left'])
            manifest.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            before = manifest.read_bytes()
            result = region_audit(manifest, root / 'coverage.json')
            coverage = result['group_class_counts_by_side']['train']
            self.assertEqual(2, sum(coverage['front']['corner_defect'].values()))
            self.assertEqual(3, sum(result['counts']['train']['corner_defect'].values()))
            self.assertEqual({'0': 0, '1': 0}, coverage['back']['corner_defect'])
            self.assertEqual({'0': 0, '1': 0}, coverage['front']['edge_defect'])
            self.assertIn({'split': 'train', 'side': 'back', 'label': 'corner_defect', 'missing_value': 0},
                          result['coverage_gaps'])
            self.assertEqual(before, manifest.read_bytes())

    def test_explicit_patches_unknown_and_test_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for row in rows:
                row['side_annotations']={'front':{'image':str(root/row['front']),'box':[.1,.1,.7,.7],
                                                 'labels':dict(row['labels'])}}
            for row in rows[:4]:
                row['side_annotations']['front']['region_labels']={
                    'upper_left':{'corner_defect':row['labels']['corner_defect'],'edge_defect':None,'surface_defect':None}}
            for row in rows[4:]:
                row['front']='missing-test.png';row['side_annotations']={'invalid':'test must not be parsed'}
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            patches,missing=region_rows(manifest)
            self.assertEqual(4,len(patches))
            self.assertTrue(all(p['split']!='test' for p in patches))
            for actual,expected in zip(patches[0]['box'],[.1,.1,.3,.3]):self.assertAlmostEqual(actual,expected)
            self.assertIsNone(patches[0]['labels']['surface_defect'])
            result=region_audit(manifest,root/'audit.json')
            self.assertEqual(['corner_defect'],result['supported'])
            self.assertTrue(result['ready_for_experiment'])
            self.assertEqual(2,result['counts']['train']['surface_defect']['None'])
            self.assertEqual(0,result['counts']['train']['surface_defect']['0'])
            self.assertTrue(any(':edge_defect' in key for key in missing))
            rows[0]['side_annotations']['front']['defect_points']=[
                {'label':'surface_defect','x':.2,'y':.2}, {'label':'edge_defect','x':.1,'y':.5}]
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertEqual((patches,missing),region_rows(manifest))
            with self.assertRaisesRegex(ValueError,'exists'):region_audit(manifest,root/'audit.json')

    def test_empty_region_labels_do_not_generate_normal_examples(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for row in rows:
                row['side_annotations']={'front':{'image':str(root/row['front']),'box':[0,0,1,1],
                                                 'labels':dict(row['labels'])}}
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=region_audit(manifest,root/'audit.json')
            self.assertEqual([],result['patches'])
            self.assertFalse(result['ready_for_experiment'])
