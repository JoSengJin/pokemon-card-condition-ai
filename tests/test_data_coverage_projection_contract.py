"""Human defect kinds stay separate when several observations share a grid cell."""
from itertools import permutations
import json
from pathlib import Path
import tempfile
import unittest

from test_pipeline import fixture
from card_condition.data_coverage import coverage_report


class CoverageProjectionContractTest(unittest.TestCase):
    def prepare(self, root):
        manifest, records = fixture(root)
        for record in records[4:]:
            record['front'] = 'missing-final.png'
            record['labels'] = 'sealed final labels'
            record['side_annotations'] = 'sealed final annotation'
        return manifest, records

    def save(self, manifest, records):
        manifest.write_text('\n'.join(json.dumps(record) for record in records))

    def cell(self, result, kind):
        return next(cell for cell in result['cells']
                    if (cell['split'],cell['side'],cell['label']) == ('train','front',kind))

    def test_three_kinds_on_one_cell_are_preserved_in_every_point_order(self):
        kinds=('corner_defect','edge_defect','surface_defect')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            record=records[1]
            annotation=dict(image=str(root/record['front']),box=[0,0,1,1],
                            labels=dict(record['labels']),visibility_issues=[])
            record['side_annotations']={'front':annotation}
            for order in permutations(kinds):
                with self.subTest(order=order):
                    annotation['defect_points']=[dict(label=kind,x=.1,y=.1) for kind in order]
                    self.save(manifest,records);before=manifest.read_bytes()
                    result=coverage_report(manifest)
                    for kind in kinds:
                        cell=self.cell(result,kind)
                        self.assertEqual((1,1),(cell['positive']['units'],cell['positive']['groups']))
                        self.assertEqual(0,cell['negative']['units'])
                        self.assertEqual(dict(points=1,groups=1),cell['typed_positive_points'])
                    self.assertEqual(3,len(result['typed_points']))
                    self.assertEqual(before,manifest.read_bytes())

    def test_edge_point_keeps_explicit_surface_zero_and_unknown_corner(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            record=records[1];labels=dict(record['labels'],corner_defect=None,surface_defect=0)
            record['side_annotations']={'front':dict(image=str(root/record['front']),box=[0,0,1,1],
                labels=labels,visibility_issues=[],defect_points=[dict(label='edge_defect',x=.1,y=.1)],
                region_labels={'upper_left':dict(corner_defect=None,edge_defect=None,surface_defect=0)})}
            self.save(manifest,records);result=coverage_report(manifest)
            targets={unit['label']:unit['target'] for unit in result['units']
                     if unit['card_id']==record['id'] and unit['side']=='front' and unit['area']=='upper_left'}
            self.assertEqual(dict(corner_defect=None,edge_defect=1,surface_defect=0),targets)
            self.assertEqual(1,self.cell(result,'edge_defect')['positive']['units'])
            self.assertEqual(1,self.cell(result,'surface_defect')['negative']['units'])
            self.assertEqual(0,self.cell(result,'corner_defect')['negative']['units'])
            self.assertEqual(dict(points=0,groups=0),self.cell(result,'surface_defect')['typed_positive_points'])


if __name__ == '__main__':
    unittest.main()
