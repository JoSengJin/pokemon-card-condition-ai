import json
from pathlib import Path
import tempfile
import unittest
from test_pipeline import fixture
from card_condition.data_coverage import coverage_report, data_coverage


class DataCoverageTest(unittest.TestCase):
    def prepare(self, root):
        manifest, records = fixture(root)
        for r in records[:4]:
            r['side_annotations'] = {'front': dict(image=str(root/r['front']), box=[0,0,1,1],
                labels=dict(r['labels']), visibility_issues=[], region_labels={})}
        # Never inspect final-test truth or images.
        for r in records[4:]:
            r['front'] = 'missing-final.png'
            r['labels'] = 'sealed final labels'
            r['side_annotations'] = 'sealed final annotation'
        return manifest, records

    def save(self, manifest, records):
        manifest.write_text('\n'.join(json.dumps(r) for r in records))

    def cell(self, result, label, split='train'):
        return next(c for c in result['cells'] if (c['split'],c['side'],c['label']) == (split,'front',label))

    def test_unknowns_face_zeros_and_final_test_stay_out(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest, records=self.prepare(root)
            self.save(manifest,records);before=manifest.read_bytes()
            result=coverage_report(manifest)
            c=self.cell(result,'surface_defect')
            self.assertEqual((0,0,18),(c['positive']['units'],c['negative']['units'],c['unknown_units']))
            self.assertFalse(c['quantity_met']);self.assertEqual(20,c['negative']['missing_units'])
            self.assertEqual(before,manifest.read_bytes())
            self.assertEqual({'train','val'},{u['split'] for u in result['units']})

    def test_same_kind_points_all_preserved_but_region_and_group_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest, records=self.prepare(root)
            a=records[1]['side_annotations']['front']
            a['defect_points']=[dict(label='surface_defect',x=.1,y=.1),dict(label='surface_defect',x=.2,y=.2),dict(label='edge_defect',x=.15,y=.15)]
            self.save(manifest,records);result=coverage_report(manifest)
            c=self.cell(result,'surface_defect')
            self.assertEqual((1,1),(c['positive']['units'],c['positive']['groups']))
            self.assertEqual(dict(points=2,groups=1),c['typed_positive_points'])
            self.assertEqual('surface_defect',next(p for p in result['typed_points'] if p['point']['x']==.2)['label'])
            self.assertEqual(dict(points=1,groups=1),self.cell(result,'edge_defect')['typed_positive_points'])

    def test_explicit_normals_under_glare_excluded_and_visibility_missing_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest, records=self.prepare(root)
            a=records[0]['side_annotations']['front'];a.pop('visibility_issues')
            a['labels']['gradable']=1
            a['region_labels']={'upper_left':dict(corner_defect=0,edge_defect=0,surface_defect=0)}
            b=records[1]['side_annotations']['front'];b['visibility_issues']=['glare'];b['glare_areas']=['upper_left']
            b['region_labels']={'upper_left':dict(corner_defect=0,edge_defect=0,surface_defect=0)}
            self.save(manifest,records);result=coverage_report(manifest)
            self.assertEqual(1,self.cell(result,'surface_defect')['negative']['units'])
            c=self.cell(result,'observation_limited')
            self.assertEqual((1,0,1),(c['positive']['units'],c['negative']['units'],c['unknown_units']))
            self.assertEqual(1,len(result['projection_skipped'])//3)

    def test_group_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root);records[2]['group']=records[0]['group']
            self.save(manifest,records)
            with self.assertRaisesRegex(ValueError,'physical-card group'):coverage_report(manifest)

    def test_photo_alias_cannot_inflate_groups(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            records[1]['front']=records[0]['front'];records[1]['side_annotations']['front']['image']=str(root/records[0]['front'])
            self.save(manifest,records)
            with self.assertRaisesRegex(ValueError,'different physical-card groups'):coverage_report(manifest)

    def test_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root);self.save(manifest,records)
            output=root/'coverage.json';data_coverage(manifest,output);before=output.read_bytes()
            with self.assertRaisesRegex(ValueError,'exists'):data_coverage(manifest,output)
            self.assertEqual(before,output.read_bytes())

    def test_many_regions_on_one_group_do_not_meet_group_minimum(self):
        from card_condition.regions import GLARE_AREAS
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root)
            for r in records[:3]:
                r['split']='train';r['group']='one-card'
                a=r['side_annotations']['front'];a['labels']['surface_defect']=0
                a['region_labels']={area:dict(corner_defect=None,edge_defect=None,surface_defect=0) for area in GLARE_AREAS}
            self.save(manifest,records);c=self.cell(coverage_report(manifest),'surface_defect')
            self.assertEqual((27,1,4),(c['negative']['units'],c['negative']['groups'],c['negative']['missing_groups']))
            self.assertFalse(c['quantity_met'])

    def test_cli_dispatch_writes_identical_audit(self):
        import contextlib,io
        from unittest.mock import patch
        from card_condition.cli import main
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,records=self.prepare(root);self.save(manifest,records)
            output=root/'cli.json'
            with patch('sys.argv',['card-condition','data-coverage',str(manifest),str(output)]),contextlib.redirect_stdout(io.StringIO()) as stdout:
                main()
            self.assertEqual(json.loads(output.read_text()),json.loads(stdout.getvalue()))
