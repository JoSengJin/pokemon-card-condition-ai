import json
import tempfile
import unittest
from pathlib import Path
from card_condition.data import LABELS
from card_condition.regions import validate_annotations
from card_condition.review import ReviewStore
from test_pipeline import fixture

class RegionsTest(unittest.TestCase):
    def test_save_export_and_stale_image_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path,rows=fixture(root)
            for r in rows:
                for side in ('front','back'): r[side]=str(root/r[side])
                r['images']=[{'path':r[s],'size':[90,130]} for s in ('front','back')]
                r.update(reviewed_by='tester',pair_verified=True)
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            store=ReviewStore(path);payload=store.snapshot();original_labels=payload['rows'][0]['labels'].copy()
            ann={'front':{'image':payload['rows'][0]['front'],'box':[.1,.1,.9,.9], 'labels':{k:None for k in LABELS},
                          'visibility_issues':['glare','perspective','shadow'],'glare_areas':['lower_right']}}
            ann['front']['labels']['corner_defect']=1
            ann['front']['region_labels']={'upper_left':{'corner_defect':1,'edge_defect':None,'surface_defect':None}}
            ann['front']['region_reviews']={'upper_left':['surface_defect']}
            ann['front']['defect_points']=[{'label':'surface_defect','x':.25,'y':.3},
                                           {'label':'edge_defect','x':.88,'y':.6}]
            payload['rows'][0]['side_annotations']=ann
            store.save(payload)
            self.assertEqual(original_labels,store.rows[0]['labels'])
            self.assertEqual(ann,store.rows[0]['side_annotations'])
            exported=store.export(store.revision)
            self.assertEqual(ann,json.loads(Path(exported['output']).read_text().splitlines()[0])['side_annotations'])
            payload=store.snapshot();payload['rows'][0]['front']=payload['rows'][0]['back'];before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'사진'): store.save(payload)
            self.assertEqual(before,path.read_bytes())
            # Omitting new metadata from a legacy client must not erase it.
            payload=store.snapshot();del payload['rows'][0]['side_annotations'];store.save(payload)
            self.assertEqual(ann,store.rows[0]['side_annotations'])

    def test_review_completion_preserves_unknown_and_rejects_invalid_targets(self):
        row={'front':'photo.png'}
        annotation={'image':'photo.png','box':[0,0,1,1],'labels':{k:None for k in LABELS},
                    'region_reviews':{'lower_right':['surface_defect']}}
        result=validate_annotations({'front':annotation},row)
        self.assertIsNone(result['front']['labels']['surface_defect'])
        self.assertNotIn('region_labels',result['front'])
        for reviews in ({'center':['corner_defect']},{'lower_right':['surface_defect','surface_defect']},
                        {'lower_right':['unknown']},{'lower_right':[]},{'unknown':['surface_defect']}):
            annotation['region_reviews']=reviews
            with self.assertRaisesRegex(ValueError,'검토 완료'):validate_annotations({'front':annotation},row)

    def test_defect_points_bounds_types_and_no_automatic_labels(self):
        row={'front':'photo.png'}
        a={'image':'photo.png','box':[.1,.1,.9,.9],'labels':{k:None for k in LABELS},
           'defect_points':[{'label':'surface_defect','x':.1,'y':.9}]}
        result=validate_annotations({'front':a},row)['front']
        self.assertEqual(a,result)
        self.assertNotIn('region_labels',result)
        self.assertTrue(all(v is None for v in result['labels'].values()))
        invalid=[None,{},[{'label':'surface_defect','x':True,'y':.5}],
                 [{'label':'surface_defect','x':float('nan'),'y':.5}],
                 [{'label':'surface_defect','x':float('inf'),'y':.5}],
                 [{'label':'surface_defect','x':.09,'y':.5}],
                 [{'label':'unknown','x':.5,'y':.5}],
                 [{'label':[],'x':.5,'y':.5}],
                 [{'label':'surface_defect','x':.5,'y':.5,'extra':1}],
                 [{'label':'surface_defect','x':.5,'y':.5}]*2]
        for points in invalid:
            a['defect_points']=points
            with self.subTest(points=points),self.assertRaisesRegex(ValueError,'결함 지점'):
                validate_annotations({'front':a},row)
        a['defect_points']=[{'label':'surface_defect','x':.5,'y':.5}];a['box']=None
        with self.assertRaisesRegex(ValueError,'결함 지점'):validate_annotations({'front':a},row)

    def test_reject_invalid_boxes_and_missing_sides(self):
        row={'front':'photo.png','back':None}
        annotation={'image':'photo.png','box':None,'labels':{k:None for k in LABELS}}
        for box in ([0,0,0,1],[-.1,0,1,1],[0,0,float('nan'),1],[True,0,1,1],[0,0,1]):
            annotation['box']=box
            with self.assertRaises(ValueError): validate_annotations({'front':annotation},row)
        annotation['box']=[0,0,1,1]
        with self.assertRaises(ValueError): validate_annotations({'back':annotation},row)
        annotation['visibility_issues']=['glare','glare']
        with self.assertRaisesRegex(ValueError,'관찰 제한'): validate_annotations({'front':annotation},row)
        annotation['visibility_issues']=['unknown']
        with self.assertRaisesRegex(ValueError,'관찰 제한'): validate_annotations({'front':annotation},row)
        annotation['visibility_issues']=[{}]
        with self.assertRaisesRegex(ValueError,'관찰 제한'): validate_annotations({'front':annotation},row)
        annotation['visibility_issues']=['glare']
        for areas in (['unknown'],['center','center'], 'center'):
            annotation['glare_areas']=areas
            with self.assertRaisesRegex(ValueError,'빛 반사 위치'): validate_annotations({'front':annotation},row)
        annotation['glare_areas']=['lower_right']
        annotation['visibility_issues']=[]
        with self.assertRaisesRegex(ValueError,'빛 반사 위치'): validate_annotations({'front':annotation},row)
        annotation['visibility_issues']=['glare'];annotation['box']=None
        with self.assertRaisesRegex(ValueError,'빛 반사 위치'): validate_annotations({'front':annotation},row)
        annotation['box']=[0,0,1,1];del annotation['glare_areas']
        self.assertEqual({'front':annotation},validate_annotations({'front':annotation},row))
        self.assertEqual({},validate_annotations({},row))

    def test_region_label_consistency_and_unknown_are_preserved(self):
        row={'front':'photo.png'}
        annotation={'image':'photo.png','box':[0,0,1,1],'labels':{k:None for k in LABELS},
                    'region_labels':{'upper_left':{'corner_defect':1,'edge_defect':None,'surface_defect':0}}}
        with self.assertRaisesRegex(ValueError,'해당 면'): validate_annotations({'front':annotation},row)
        annotation['labels']['corner_defect']=1
        result=validate_annotations({'front':annotation},row)
        self.assertIsNone(result['front']['region_labels']['upper_left']['edge_defect'])
        self.assertEqual(0,result['front']['region_labels']['upper_left']['surface_defect'])
        annotation['region_labels']['center']=annotation['region_labels'].pop('upper_left')
        with self.assertRaisesRegex(ValueError,'모서리'): validate_annotations({'front':annotation},row)
        annotation['region_labels']={'unknown':{'corner_defect':None,'edge_defect':None,'surface_defect':None}}
        with self.assertRaisesRegex(ValueError,'유효한'): validate_annotations({'front':annotation},row)
        annotation['region_labels']={'upper_left':{'corner_defect':True,'edge_defect':None,'surface_defect':None}}
        with self.assertRaisesRegex(ValueError,'0, 1'): validate_annotations({'front':annotation},row)

    def test_surface_types_and_observation_points_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path,rows=fixture(root)
            for r in rows:
                for side in ('front','back'):r[side]=str(root/r[side])
                r['images']=[{'path':r[s],'size':[90,130]} for s in ('front','back')]
                r.update(reviewed_by='tester',pair_verified=True)
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            store=ReviewStore(path);payload=store.snapshot()
            a={'image':payload['rows'][0]['front'],'box':[0,0,1,1],'labels':{k:None for k in LABELS},
               'visibility_issues':['glare','blur'],'glare_areas':['center'],
               'defect_points':[{'label':'surface_defect','x':.2,'y':.3,'types':['scratch','crease','stain']}],
               'visibility_points':[{'issue':'glare','x':.5,'y':.5},{'issue':'blur','x':.7,'y':.7}]}
            payload['rows'][0]['side_annotations']={'front':a};store.save(payload)
            reloaded=ReviewStore(path)
            self.assertEqual(a,reloaded.rows[0]['side_annotations']['front'])
            exported=store.export(store.revision)
            self.assertEqual(a,json.loads(Path(exported['output']).read_text().splitlines()[0])['side_annotations']['front'])
            self.assertIsNone(reloaded.rows[0]['side_annotations']['front']['labels']['surface_defect'])

    def test_invalid_surface_types_and_observation_points_rejected(self):
        a={'image':'photo.png','box':[0,0,1,1],'labels':{k:None for k in LABELS},'visibility_issues':['glare']}
        for types in (None,[],['unknown'],['scratch','scratch'],[{}]):
            a['defect_points']=[{'label':'surface_defect','x':.2,'y':.3,'types':types}]
            with self.subTest(types=types),self.assertRaises(ValueError):validate_annotations({'front':a},{'front':'photo.png'})
        a['defect_points']=[]
        for points in ([{'issue':'blur','x':.5,'y':.5}],[{'issue':'glare','x':1.1,'y':.5}],
                       [{'issue':'glare','x':True,'y':.5}],[{'issue':'glare','x':.5,'y':.5}]*2):
            a['visibility_points']=points
            with self.subTest(points=points),self.assertRaises(ValueError):validate_annotations({'front':a},{'front':'photo.png'})
