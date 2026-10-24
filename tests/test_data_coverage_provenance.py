"""Synthetic counterexamples for data-coverage provenance; no real labels or photos.

Each test states an invariant the audit should keep. A failure reproduces the
counterexample described in docs/collaboration/reports/data-coverage-provenance-20261025.md.
"""
import json
from pathlib import Path
import tempfile
import unittest
from test_pipeline import fixture
from card_condition.data_coverage import coverage_report


class DataCoverageProvenanceTest(unittest.TestCase):
    def prepare(self, root):
        manifest, records = fixture(root)
        for r in records[4:]:
            r['front'] = 'missing-final.png'
            r['labels'] = 'sealed final labels'
            r['side_annotations'] = 'sealed final annotation'
        return manifest, records

    def save(self, manifest, records):
        manifest.write_text('\n'.join(json.dumps(r) for r in records))

    def cell(self, result, label, side='front', split='train'):
        return next(c for c in result['cells'] if (c['split'],c['side'],c['label']) == (split,side,label))

    def test_off_target_typed_point_is_projected_or_traced(self):
        # Finding 1: a corner click in the middle_right cell is kept as a typed point,
        # but no corner region unit exists there and no skip reason is written.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            r=records[1]
            r['side_annotations']={'front':dict(image=str(root/r['front']),box=[0,0,1,1],labels=dict(r['labels']),
                visibility_issues=[],defect_points=[dict(label='corner_defect',x=.95,y=.4)])}
            self.save(manifest,records);result=coverage_report(manifest)
            c=self.cell(result,'corner_defect')
            self.assertEqual(dict(points=1,groups=1),c['typed_positive_points'])
            self.assertEqual(0,c['positive']['units'])
            expected=dict(card_id=r['id'],side='front',label='corner_defect',
                          area='middle_right',reason='point_outside_target_area')
            traced=[s for s in result['skipped'] if all(s.get(k)==v for k,v in expected.items())]
            self.assertEqual(1,len(traced),'typed point dropped from region units without its exact skip record')

    def test_one_decoded_photo_assigned_to_both_sides_is_rejected(self):
        # Finding 3: a non-gradable record may reuse one photo for front and back.
        # Choosing either side would invent provenance, so the audit must refuse the input.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            r=records[0]
            self.assertEqual(0,r['labels']['gradable'])
            r['side_annotations']={side:dict(image=str(root/r[side]),box=[0,0,1,1],labels=dict(r['labels']),
                visibility_issues=['blur']) for side in ('front','back')}
            # Control: distinct front/back photos with the same annotations are accepted.
            self.save(manifest,records);coverage_report(manifest)
            r['back']=r['front'];r['side_annotations']['back']['image']=str(root/r['front'])
            self.save(manifest,records)
            with self.assertRaises(ValueError,msg='one decoded photo was accepted as both front and back'):
                coverage_report(manifest)


if __name__ == '__main__':
    unittest.main()
