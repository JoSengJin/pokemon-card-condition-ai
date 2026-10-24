import json
from pathlib import Path
import tempfile
import unittest

from card_condition.point_dataset import point_box, point_dataset, point_rows, point_for_label
from card_condition.region_experiment import experiment, group_training_weights, training_class_ratios
from card_condition.region_model import RegionAnalyzer
from card_condition.regions import region_box
from card_condition.data import load_manifest
import torch
from card_condition.side_experiment import side_tensor
from test_pipeline import fixture


class PointDatasetTest(unittest.TestCase):
    def test_grid_keeps_each_defect_kind_coordinate_in_a_shared_region(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            row = rows[1]
            labels = dict(row['labels'], corner_defect=1, edge_defect=1, surface_defect=1)
            points = [dict(label='corner_defect', x=.1, y=.1),
                      dict(label='edge_defect', x=.2, y=.2),
                      dict(label='surface_defect', x=.3, y=.3)]
            row['side_annotations'] = {'front': dict(image=str(root/row['front']),
                box=[0,0,1,1], labels=labels, defect_points=points)}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows)); before = manifest.read_bytes()
            patches, _ = point_rows(manifest, grid=True)
            patch = next(p for p in patches if p['card_id'] == row['id'])
            self.assertEqual({p['label']:p for p in points}, patch['point_by_label'])
            self.assertEqual(points[0], patch['point'])
            for point in points:
                self.assertEqual(point, point_for_label(patch, point['label']))
            self.assertEqual(before, manifest.read_bytes())

    def test_point_selector_never_promotes_another_kind_or_a_region_label(self):
        corner = dict(label='corner_defect', x=.1, y=.1)
        row = dict(point=corner, labels=dict(corner_defect=1, surface_defect=1))
        self.assertIsNone(point_for_label(row, 'surface_defect'))
        self.assertEqual(corner, point_for_label(row, 'corner_defect'))
        row['point_by_label'] = {'surface_defect': corner}
        with self.assertRaisesRegex(ValueError, 'match'):
            point_for_label(row, 'surface_defect')
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            point_for_label(row, 'unknown')

    def test_all_saved_points_become_local_training_rows_without_normal_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            row=rows[1];labels={k:None for k in row['labels']};labels['edge_defect']=1
            points=[dict(label='edge_defect',x=.1,y=.2),dict(label='edge_defect',x=.1,y=.5),dict(label='edge_defect',x=.2,y=.9)]
            row['side_annotations']={'front':dict(image=str(root/row['front']),box=[0,0,1,1],labels=labels,defect_points=points)}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows));before=manifest.read_bytes()
            patches,_=point_rows(manifest,splits={'train'})
            actual=[p for p in patches if p['card_id']==row['id']]
            self.assertEqual([p['point'] for p in actual],points)
            self.assertTrue(all(p['labels']==dict(corner_defect=None,edge_defect=1,surface_defect=None) for p in actual))
            self.assertTrue(all(p['group']==row['group'] and p['split']=='train' for p in actual))
            self.assertEqual(manifest.read_bytes(),before)

    def test_partial_stain_clicks_do_not_imply_normal_or_whole_face_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve(); manifest,rows=fixture(root)
            row=rows[1]
            row['labels']['surface_defect']=1
            row['notes']='앞면 전반적으로 오염이 있지만 모든 위치를 클릭하지 않았음'
            row['side_annotations']={'front':dict(image=str(root/row['front']),box=[0,0,1,1],
                labels=dict(row['labels']),region_labels={},box_reviewed=True,
                defect_points=[dict(label='surface_defect',x=.1,y=.1),
                               dict(label='surface_defect',x=.12,y=.12),
                               dict(label='surface_defect',x=.8,y=.8)])}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            patches,_=point_rows(manifest,grid=True,splits={'train'})
            actual=[p for p in patches if p['card_id']==row['id']]
            self.assertEqual({p['area'] for p in actual},{'upper_left','lower_right'})
            self.assertTrue(all(p['labels']==dict(corner_defect=None,edge_defect=None,surface_defect=1) for p in actual))

    def test_class_balance_uses_train_group_mass_only(self):
        def row(split, group, value):
            return dict(split=split,group=group,labels=dict(corner_defect=None,edge_defect=None,surface_defect=value))
        rows=[row('train','normal',0)]*4+[row('train','defect1',1),row('train','defect2',1),
              row('train','unknown',None),row('val','normal-val',0)]
        weights=group_training_weights(rows,['surface_defect'])
        ratios=training_class_ratios(rows,weights,['surface_defect'])
        self.assertEqual([1.0,1.0,.5],ratios)
        rows[-1]['labels']['surface_defect']=1
        self.assertEqual(ratios,training_class_ratios(rows,weights,['surface_defect']))
        self.assertEqual(0,weights[-2][-1]);self.assertEqual(0,weights[-1][-1])
        with self.assertRaisesRegex(ValueError,'both known classes'):
            training_class_ratios(rows[4:],weights[4:],['surface_defect'])

    def test_local_evidence_does_not_require_whole_card_gradability(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            row=rows[1]
            row['labels']['gradable']=None
            row['side_annotations']={'front':dict(image=str(root/row['front']),box=[0,0,1,1],
                labels=dict(row['labels']),defect_points=[dict(label='surface_defect',x=.2,y=.2)])}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before=manifest.read_bytes()
            with self.assertRaisesRegex(ValueError,'gradable label'):load_manifest(manifest)
            patches,_=point_rows(manifest)
            self.assertEqual(1,len(patches))
            self.assertEqual(1,patches[0]['labels']['surface_defect'])
            self.assertEqual(before,manifest.read_bytes())
            row['side_annotations']['front']['region_reviews']={'lower_center':['edge_defect']}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            reviewed_patches,_=point_rows(manifest)
            self.assertEqual(patches,reviewed_patches)
            self.assertTrue(all(p['labels']['edge_defect'] is None for p in reviewed_patches))
            rows[1]['labels']['gradable']='invalid'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError,'Labels'):point_rows(manifest)

    def test_grid_experiment_deduplicates_and_keeps_validation_separate(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            for i in range(4):
                a = dict(image=str(root/rows[i]['front']),box=[0,0,1,1],labels=dict(rows[i]['labels']))
                if i % 2:
                    a['defect_points'] = [dict(label='surface_defect',x=.1,y=.1),
                                          dict(label='surface_defect',x=.2,y=.2)]
                else:
                    a['region_labels'] = {'center':dict(corner_defect=None,edge_defect=None,surface_defect=0)}
                rows[i]['side_annotations'] = {'front':a}
            for row in rows[4:]: row['front'] = 'missing-test.png'
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            patches, audit = point_rows(manifest,grid=True)
            self.assertTrue(audit['ready_for_experiment'])
            self.assertEqual(4,len(patches))
            self.assertEqual(2,len(audit['skipped']))
            for p in patches: self.assertEqual(region_box(p['card_box'],p['area']),p['box'])
            self.assertEqual([0,0,1],group_training_weights(patches,['surface_defect'],'val')[-1])
            report = experiment(manifest,root/'model',epochs=2,device='cpu',pretrained=False,point_grid=True)
            self.assertEqual('point_validation',report['evaluation_kind'])
            self.assertEqual(['surface_defect'],report['supported'])
            self.assertEqual(2,sum(report['metrics']['surface_defect'].values()))
            self.assertTrue(report['group_balance'])
            self.assertTrue(all(r['split']=='val' for r in report['predictions']))
            self.assertIn('equal group',report['selection_metric'])
            balanced = experiment(manifest,root/'balanced',epochs=2,device='cpu',pretrained=False,point_grid=True,balance=True)
            self.assertTrue(balanced['balance'])
            self.assertEqual(report['selection_metric'],balanced['selection_metric'])
            self.assertEqual(report['counts'],balanced['counts'])
            self.assertEqual(1.0,balanced['positive_weights']['surface_defect'])
            self.assertEqual(report['predictions'],balanced['predictions'])
            self.assertTrue(torch.load(root/'balanced/model.pt',weights_only=True)['balance'])
            self.assertEqual(before,manifest.read_bytes())
            self.assertEqual(4,len((root/'model/inputs.jsonl').read_text().splitlines()))
            analyzer=RegionAnalyzer(root/'model/model.pt','cpu')
            for prediction in report['predictions']:
                actual=analyzer.analyze(prediction['image'],prediction['card_box'],prediction['area'])
                self.assertAlmostEqual(prediction['probabilities']['surface_defect'],
                    actual['probabilities']['surface_defect'],places=6)
                self.assertTrue(actual['requires_gemini'])
            rows[3]['side_annotations']['front']['defect_points'] = []
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError,'point classes'):
                experiment(manifest,root/'blocked',pretrained=False,point_grid=True)
            self.assertFalse((root/'blocked').exists())

    def test_grid_retains_existing_human_positive_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=fixture(root)
            for i in (1,3):
                rows[i]['side_annotations']={'front':dict(image=str(root/rows[i]['front']),box=[0,0,1,1],
                    labels=dict(rows[i]['labels']),
                    region_labels={'upper_left':dict(corner_defect=1,edge_defect=None,surface_defect=1),
                                   'center':dict(corner_defect=None,edge_defect=None,surface_defect=1)},
                    defect_points=[dict(label='surface_defect',x=.1,y=.1)])}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            patches,_=point_rows(manifest,grid=True)
            self.assertEqual(4,len(patches))
            self.assertEqual(4,sum(p['labels']['surface_defect']==1 for p in patches))
            self.assertEqual(2,sum(p['labels']['corner_defect']==1 for p in patches))
            rows[1]['side_annotations']['front']['region_labels']['upper_left']['surface_defect']=0
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError,'Conflicting human point'):
                point_rows(manifest,grid=True)

    def test_crops_targets_groups_limits_and_test_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            for i in range(4):
                labels = dict(rows[i]['labels'], surface_defect=1 if i == 1 else 0)
                rows[i]['side_annotations'] = {'front': dict(image=str(root/rows[i]['front']),
                    box=[.1,.1,.7,.7], labels=labels,
                    region_labels={'lower_right': dict(corner_defect=None, edge_defect=None, surface_defect=0)})}
            ann = rows[1]['side_annotations']['front']
            ann['defect_points'] = [dict(label='surface_defect',x=.1,y=.1),
                                    dict(label='surface_defect',x=.4,y=.4)]
            # Explicit normal within a limited region must not become a training negative.
            rows[2]['side_annotations']['front'].update(visibility_issues=['glare'],glare_areas=['lower_right'])
            # A point contradicting a non-positive face label is withheld.
            rows[3]['side_annotations']['front']['defect_points'] = [dict(label='surface_defect',x=.7,y=.7)]
            for row in rows[4:]:
                row['front'] = 'missing-test.png'; row['side_annotations'] = {'invalid': 'not read'}
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            result = point_dataset(manifest,root/'out')
            patches = [json.loads(line) for line in (root/'out/patches.jsonl').read_text().splitlines()]
            self.assertEqual(before,manifest.read_bytes())
            self.assertFalse(result['ready_for_experiment'])
            self.assertEqual(2,result['counts']['train']['surface_defect']['1'])
            self.assertEqual(1,result['group_class_counts']['train']['surface_defect']['1'])
            self.assertEqual({'observation_limited','face_not_positive','point_in_normal_region'},
                             {entry['reason'] for entry in result['skipped']})
            self.assertTrue(any(x == dict(split='val',label='surface_defect',value=1) for x in result['missing_classes']))
            for patch in patches:
                self.assertIsNone(patch['labels']['corner_defect'])
                self.assertIsNone(patch['labels']['edge_defect'])
                self.assertEqual((3,224,224),tuple(side_tensor(patch['image'],patch['box'],crop=True).shape))
            with self.assertRaisesRegex(ValueError,'exists'): point_dataset(manifest,root/'out')

    def test_edge_points_remain_inside_crop(self):
        box = [.1,.1,.7,.7]
        for x,y in ((.1,.1),(.7,.7),(.7,.1),(.1,.7),(.4,.4)):
            crop = point_box(box,dict(x=x,y=y))
            self.assertAlmostEqual(.2,crop[2]-crop[0])
            self.assertAlmostEqual(.2,crop[3]-crop[1])
            self.assertLessEqual(crop[0],x); self.assertLessEqual(x,crop[2])
            self.assertLessEqual(crop[1],y); self.assertLessEqual(y,crop[3])
            self.assertGreaterEqual(crop[0],box[0]); self.assertLessEqual(crop[2],box[2])
            self.assertGreaterEqual(crop[1],box[1]); self.assertLessEqual(crop[3],box[3])

    def test_explicit_normal_perspective_region_is_kept_but_blur_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); manifest, rows = fixture(root)
            annotation = dict(image=str(root/rows[0]['front']), box=[0,0,1,1],
                box_reviewed=True, labels=rows[0]['labels'], visibility_issues=['perspective'],
                region_labels={'upper_left':dict(corner_defect=None,edge_defect=0,surface_defect=None)})
            rows[0]['side_annotations'] = {'front':annotation}
            manifest.write_text('\n'.join(json.dumps(row) for row in rows))
            patches, report = point_rows(manifest, grid=True)
            self.assertEqual(0, next(p for p in patches if p['card_id']=='0')['labels']['edge_defect'])
            self.assertFalse(any(r['card']=='0' for r in report['skipped']))
            annotation['box_reviewed'] = False
            manifest.write_text('\n'.join(json.dumps(row) for row in rows))
            patches, report = point_rows(manifest, grid=True)
            self.assertFalse(any(p['card_id']=='0' for p in patches))
            self.assertTrue(any(r['card']=='0' and r['reason']=='observation_limited' for r in report['skipped']))
            annotation['box_reviewed'] = True
            annotation['visibility_issues'] = ['perspective','blur']
            manifest.write_text('\n'.join(json.dumps(row) for row in rows))
            patches, report = point_rows(manifest, grid=True)
            self.assertFalse(any(p['card_id']=='0' for p in patches))
            self.assertIn(dict(card='0',side='front',area='upper_left',label='edge_defect',
                reason='observation_limited'), report['skipped'])
