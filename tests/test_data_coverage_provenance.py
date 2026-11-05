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


    def test_in_target_point_has_no_outside_target_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            r=records[1]
            r['side_annotations']={'front':dict(image=str(root/r['front']),box=[0,0,1,1],labels=dict(r['labels']),
                visibility_issues=[],defect_points=[dict(label='corner_defect',x=.1,y=.1)])}
            self.save(manifest,records);result=coverage_report(manifest)
            self.assertEqual(1,self.cell(result,'corner_defect')['positive']['units'])
            self.assertEqual(dict(points=1,groups=1),self.cell(result,'corner_defect')['typed_positive_points'])
            self.assertFalse(any(s['reason']=='point_outside_target_area' for s in result['skipped']))

    def test_distinct_paths_with_identical_pixels_on_both_sides_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            r=records[0]
            (root/r['back']).write_bytes((root/r['front']).read_bytes())
            self.save(manifest,records)
            with self.assertRaisesRegex(ValueError,'both front and back'):
                coverage_report(manifest)

    def test_photo_side_is_consistent_across_records_but_same_side_can_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            first,alias=records[:2]
            first['back']=None
            first['side_annotations']={'front':dict(image=str(root/first['front']),box=[0,0,1,1],
                labels=dict(first['labels']),visibility_issues=['blur'])}
            alias.update(group=first['group'],front=first['front'],back=None,labels=dict(first['labels']))
            alias['side_annotations']={'front':dict(first['side_annotations']['front'])}
            self.save(manifest,records)
            self.assertEqual(1,self.cell(coverage_report(manifest),'observation_limited')['positive']['units'])
            alias.update(front=None,back=first['front'])
            alias['side_annotations']={'back':dict(first['side_annotations']['front'])}
            self.save(manifest,records)
            with self.assertRaisesRegex(ValueError,'both front and back'):
                coverage_report(manifest)


if __name__ == '__main__':
    unittest.main()
