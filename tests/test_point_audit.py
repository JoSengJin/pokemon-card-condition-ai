import json
from pathlib import Path
import tempfile
import unittest

from card_condition.point_audit import point_audit
from card_condition.regions import region_box
from test_pipeline import fixture


class PointAuditTest(unittest.TestCase):
    def test_location_conflict_unknown_and_test_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            row = rows[0]
            row['labels']['gradable'] = None
            row['side_annotations'] = {'front': {'image': str(root / row['front']),
                'box': [.1, .1, .7, .7], 'labels': dict(row['labels']),
                'region_labels': {'upper_left': dict(corner_defect=None, edge_defect=None, surface_defect=0)},
                'defect_points': [dict(label='surface_defect', x=.15, y=.15),
                                  dict(label='surface_defect', x=.7, y=.7),
                                  dict(label='surface_defect', x=.4, y=.4),
                                  dict(label='surface_defect', x=region_box([.1,.1,.7,.7], 'center')[0],
                                       y=region_box([.1,.1,.7,.7], 'center')[1])]}}
            rows[1]['side_annotations'] = {'front': {'image': str(root / rows[1]['front']),
                'box': [0, 0, 1, 1], 'labels': dict(rows[1]['labels']),
                'region_labels': {'lower_right': dict(corner_defect=1, edge_defect=None, surface_defect=None)},
                'defect_points': [dict(label='corner_defect', x=1, y=1)]}}
            for row in rows[4:]:
                row['front'] = 'missing-test.png'; row['side_annotations'] = {'invalid': 'must not be read'}
            manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            before = manifest.read_bytes()
            result = point_audit(manifest, root/'audit.json')
            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(['upper_left','lower_right','center','center','lower_right'],
                             [p['area'] for p in result['points']])
            self.assertEqual(dict(matches_positive=1, conflicts_with_normal=1, region_unknown=3), result['counts'])
            self.assertIsNone(result['points'][1]['region_label'])
            self.assertEqual(0, result['training_targets_created'])
            self.assertFalse(result['labels_modified'])
            with self.assertRaisesRegex(ValueError,'exists'): point_audit(manifest,root/'audit.json')
