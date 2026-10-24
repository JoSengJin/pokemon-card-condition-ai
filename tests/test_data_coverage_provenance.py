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
            traced=[s for s in result['skipped']+result['projection_skipped']
                    if s.get('card_id',s.get('card'))==r['id'] and s.get('side')=='front']
            self.assertTrue(traced,'typed point dropped from region units without a skip reason')

    def test_one_decoded_photo_counts_on_one_side_only(self):
        # Finding 3: a non-gradable record may reuse one photo for front and back;
        # the audit then counts the same pixels in both side cells.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            r=records[0];r['back']=r['front']
            self.assertEqual(0,r['labels']['gradable'])
            r['side_annotations']={side:dict(image=str(root/r['front']),box=[0,0,1,1],labels=dict(r['labels']),
                visibility_issues=['blur']) for side in ('front','back')}
            self.save(manifest,records);result=coverage_report(manifest)
            front=self.cell(result,'observation_limited','front');back=self.cell(result,'observation_limited','back')
            self.assertEqual(1,front['positive']['units']+back['positive']['units'],
                             'one decoded photo was counted as both front and back')


if __name__ == '__main__':
    unittest.main()
