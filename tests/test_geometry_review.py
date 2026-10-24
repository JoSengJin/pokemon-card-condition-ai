import copy
import json
from pathlib import Path
import tempfile
import unittest

from card_condition.geometry_review import geometry_tasks,prepare_geometry_review
from card_condition.regions import validate_annotations
from card_condition.review import ReviewStore
import test_visibility_model


class GeometryReviewTest(unittest.TestCase):
    def test_plan_train_only_and_confirmation_survives_save(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            # The test fixture's invalid test photos must never be opened.
            before=manifest.read_bytes()
            result=prepare_geometry_review(manifest,root/'plan')
            self.assertEqual(1,len(result['tasks']))
            modified=copy.deepcopy(rows[1])
            modified['side_annotations']['front']['box']=[.1,.1,.9,.9]
            modified['side_annotations']['front']['box_reviewed']=False
            self.assertEqual(1,len(geometry_tasks([modified])))
            self.assertEqual('train',result['split'])
            self.assertEqual(before,manifest.read_bytes())
            row=next(r for r in rows if r['id']==result['tasks'][0]['card'])
            row['side_annotations']['front']['box_reviewed']=True
            self.assertEqual([],geometry_tasks([row]))
            annotation=copy.deepcopy(row['side_annotations'])
            annotation['front']['box_reviewed']='true'
            with self.assertRaisesRegex(ValueError,'카드 영역 확인'):
                validate_annotations(annotation,row)
            row['side_annotations']['front']['box_reviewed']=True
            # ReviewStore needs image inventory, not the deliberately invalid test fixture.
            train=[r for r in rows if r['split']=='train']
            for record in train:
                record['images']=[dict(path=record[side],size=[40,40]) for side in ('front','back')]
            manifest.write_text('\n'.join(json.dumps(r) for r in train))
            store=ReviewStore(manifest)
            payload=store.snapshot()
            saved=store.save(payload)
            matched=next(r for r in saved['rows'] if r['id']==row['id'])
            self.assertTrue(matched['side_annotations']['front']['box_reviewed'])
            self.assertEqual(row['side_annotations']['front']['labels'],matched['side_annotations']['front']['labels'])
            self.assertEqual([],prepare_geometry_review(manifest,root/'next')['tasks'])

    def test_three_physical_groups_no_defect_rechecks(self):
        label=dict(gradable=None,centering_defect=None,corner_defect=None,edge_defect=None,surface_defect=None)
        rows=[dict(id=str(i),group=str(i),split='train',front=str(i),side_annotations={
            'front':dict(image=str(i),box=[0,0,1,1],labels=label,visibility_issues=['glare'])}) for i in range(5)]
        self.assertEqual(3,len(geometry_tasks(rows)))
        rows[0]['side_annotations']['front']['defect_points']=[dict(x=.5,y=.5,label='surface_defect')]
        rows[0]['side_annotations']['front']['labels']=dict(label,surface_defect=1)
        self.assertIn('0',[t['card'] for t in geometry_tasks(rows)])
        rows[0]['side_annotations']['front']['region_labels']={'center':dict(corner_defect=None,edge_defect=None,surface_defect=1)}
        self.assertNotIn('0',[t['card'] for t in geometry_tasks(rows)])
