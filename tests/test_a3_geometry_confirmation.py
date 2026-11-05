import copy
import importlib.util
from pathlib import Path
import unittest
import torch

path=Path(__file__).resolve().parents[1]/'tools/experiments/a3-geometry-confirmation-20261030/worker.py'
spec=importlib.util.spec_from_file_location('geometry_worker',path);W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)


class GeometryConfirmationTest(unittest.TestCase):
    def test_reuse_keeps_feature_order_and_marks_only_new_rows(self):
        a=dict(id='a',group='g',image_sha256='sha',box=[0,0,1,1],card_box=[0,0,1,1],target=1,side='front',split='val')
        b=dict(a,id='b');c=dict(a,id='c')
        cache=dict(rows=[a,b],features=torch.tensor([[[1.]],[[2.]]]))
        x,reused,missing=W.reuse_features([b,c,a],cache)
        self.assertEqual(reused,[(0,1),(2,0)]);self.assertEqual(missing,[1]);self.assertEqual(x[[0,2]].tolist(),[[[2.]],[[1.]]])
        for key,value in [('image_sha256','changed'),('group','other'),('box',[0,0,.5,1]),('target',0)]:
            with self.subTest(key=key),self.assertRaises(ValueError):W.reuse_features([dict(a,**{key:value}),b],cache)
        with self.assertRaises(ValueError):W.reuse_features([a],cache)
        with self.assertRaises(ValueError):W.reuse_features([a,a,b],cache)

    def test_all_four_frozen_guards_keep_truth_and_actual_point_scores(self):
        rows=[dict(id=s,group=s,image_sha256=s,box=[0,0,1,1],target=1,side=s,split='val') for s in ('front','back')]
        points=[dict(rows[i],id=s+'-point',point=dict(x=.2,y=.2,label='surface_defect'),parent_index=i,human_token=0) for i,s in enumerate(('front','back'))]
        cohorts=[]
        for i,side in enumerate(('front','back')):
            cohorts += [dict(id=f'a3-reviewed-surface-{side}-regions',rows=[rows[i]],point_ids=[]),dict(id=f'a3-reviewed-surface-{side}-points',rows=[points[i]],point_ids=[points[i]['id']])]
        reference=dict(required_cohorts=cohorts);maps=torch.tensor([[.7,.8],[.6,.9]]);masks=torch.ones((2,2),dtype=torch.bool)
        result=W.extend_observations(reference,dict(required_cohorts=[]),rows,points,maps,masks)
        self.assertAlmostEqual(result['required_cohorts'][1]['point_scores'][0],.7)
        self.assertEqual(result['required_cohorts'][2]['rows'],[rows[1]])
        for changed in [dict(required_cohorts=cohorts[:-1]),dict(required_cohorts=list(reversed(cohorts)))]:
            if len(changed['required_cohorts'])<4:
                with self.assertRaises(ValueError):W.extend_observations(changed,dict(required_cohorts=[]),rows,points,maps,masks)
        broken=copy.deepcopy(reference);broken['required_cohorts'][1]['rows'][0]['point']['x']=.3
        with self.assertRaises(ValueError):W.extend_observations(broken,dict(required_cohorts=[]),rows,points,maps,masks)
