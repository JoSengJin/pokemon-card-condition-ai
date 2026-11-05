import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODULES = {}
for name in ('data', 'readout', 'report'):
    spec = importlib.util.spec_from_file_location('test_a3_'+name, ROOT/'tools/experiments/a3-surface-transfer-20261029'/f'{name}.py')
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded); MODULES[name] = loaded
D, R, P = (MODULES[n] for n in ('data','readout','report'))


class SurfaceTransferTest(unittest.TestCase):
    def test_projection_preserves_unknown_geometry_and_point_parent(self):
        row = dict(card_id='a',group='g',side='front',split='val',image='x',image_sha256='sha',
                   card_box=[0,0,1,1],box_reviewed=True,label='surface_defect',target=1,area='center')
        point = dict(row,point=dict(x=1/3,y=1/3,label='surface_defect'))
        original = dict(units=[row,dict(row,card_id='b',image_sha256='other',box_reviewed=False),dict(row,target=None,area='upper_left'),dict(row,split='train')],
                        typed_points=[point,dict(point,card_id='b',image_sha256='other',box_reviewed=False)])
        saved = copy.deepcopy(original)
        rows, points, missing = D.surface_rows(original)
        self.assertEqual((len(rows),len(points),len(missing)),(1,1,2)); self.assertEqual(points[0]['parent_index'],0)
        self.assertEqual(rows[0]['box'],[1/3,1/3,2/3,2/3]); self.assertEqual(original,saved)
        original['units'][0]['target']=0
        with self.assertRaisesRegex(ValueError,'positive region'): D.surface_rows(original)

    def test_boundary_point_mapping_and_padding_with_exif(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'portrait.jpg'; exif=Image.Exif();exif[274]=6
            Image.new('RGB',(90,30),'white').save(path,exif=exif)
            rows=[dict(image=str(path),box=[0,0,1,1])]
            points=[dict(parent_index=0,point=dict(x=x,y=y)) for x,y in [(0,0),(1,1),(.5,.5)]]
            masks,mapped=D.point_tokens(rows,points)
            self.assertEqual(len(mapped),3);self.assertLess(int(masks[0].sum()),256)
            self.assertTrue(all(masks[0][p['human_token']] for p in mapped))
            self.assertTrue(all(0<=v<=223 for p in mapped for v in p['input_pixel']))
            with self.assertRaises(ValueError):D.point_tokens(rows,[dict(parent_index=0,point=dict(x=1.1,y=0))])

    def test_average_probabilities_before_physical_max(self):
        x=torch.tensor([[[1.],[-1.],[100.]]])
        heads=[dict(coef=torch.tensor([2.]),bias=torch.tensor(0.)),dict(coef=torch.tensor([-2.]),bias=torch.tensor(0.))]
        maps=R.mean_maps(x,heads);self.assertTrue(torch.allclose(maps,torch.full((1,3),.5)))
        self.assertAlmostEqual(R.region_scores(maps,torch.tensor([[True,True,False]]))[0],.5)
        with self.assertRaises(ValueError):R.mean_maps(x,[])
        with self.assertRaises(ValueError):R.mean_maps(x,[dict(coef=torch.tensor([float('nan')]),bias=torch.tensor(0.))])
        with self.assertRaises(ValueError):R.region_scores(maps,torch.zeros((1,3),dtype=torch.bool))
        with self.assertRaises(ValueError):R.region_scores(torch.tensor([[float('nan')]]),torch.ones((1,1),dtype=torch.bool))

    def test_raw_decoded_group_and_unresolved_training_guards(self):
        train=[dict(id='t',group='train',image='/train')]; val=[dict(id='v',group='val',image='/val')]
        identity={'/train':{'raw1','decoded1'},'/val':{'raw2','decoded2'}};heads=[dict(train_ids=['t'])]
        self.assertEqual(D.check_separation(heads,train,val,identity)['photo_overlap'],0)
        with self.assertRaises(ValueError):D.check_separation([dict(train_ids=['unknown'])],train,val,identity)
        with self.assertRaises(ValueError):D.check_separation(heads,train,[dict(val[0],group='train')],identity)
        identity['/val'].add('decoded1')
        with self.assertRaises(ValueError):D.check_separation(heads,train,val,identity)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x.png';Image.new('RGB',(4,4),'red').save(path)
            sha=D.decoded_hash(path.read_bytes())[0]; rows=[dict(image=str(path),image_sha256=sha)]
            ids,raw=D.photo_identities(rows);self.assertIn(sha,ids[str(path.resolve())])
            Image.new('RGB',(4,4),'blue').save(path)
            with self.assertRaises(ValueError):D.photo_identities(rows)

    def test_held_fold_replay_and_required_point_observations(self):
        rows=[dict(id='f',side='front',group='f',target=1),dict(id='b',side='back',group='b',target=0)]
        training=rows+[dict(id='train',group='t')]
        head=dict(coef=torch.tensor([1.]),bias=torch.tensor(0.),train_ids=['train'])
        proposal=dict(folds=[dict(id='fold',held_ids=['f'],train_ids=['train'])])
        maps=R.replay_maps(rows,training,torch.tensor([[[1.],[-1.]],[[2.],[-2.]]]),[dict(head,fold='fold')],[dict(head,group='b')],proposal)
        typed=[dict(id='point',parent_index=0,human_token=1)];old=[dict(id='old',parent_index=0)]
        reference=dict(rows=rows,required_cohorts=[dict(id='typed',rows=typed,point_ids=['point'])])
        fixed=dict(point_reference=dict(rows=old),typed_point_reference=dict(rows=typed))
        obs=R.observations(reference,fixed,dict(point_tokens=torch.tensor([0])),maps,torch.ones((2,2),dtype=torch.bool))
        self.assertAlmostEqual(obs['required_cohorts'][0]['point_scores'][0],float(torch.sigmoid(torch.tensor(-1.))))
        reference['required_cohorts'][0]['rows']=[dict(id='unknown')]
        with self.assertRaises(ValueError):R.observations(reference,fixed,dict(point_tokens=torch.tensor([0])),maps,torch.ones((2,2),dtype=torch.bool))
        with self.assertRaises(ValueError):R.replay_maps(rows,training,torch.ones((2,2,1)),[dict(head,fold='fold',train_ids=['f'])],[dict(head,group='b')],proposal)

    def test_paired_metrics_missing_support_and_photo_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'photo.png';Image.new('RGB',(40,40),'white').save(path)
            rows=[dict(id='front & positive',side='front',group='f',target=1,image=str(path),box=[0,0,1,1]),dict(id='back negative',side='back',group='b',target=0,image=str(path),box=[0,0,1,1])]
            points=[dict(id='point',side='front',group='f',parent_index=0,input_pixel=[20,20])]
            result=P.compare(rows,points,[.4,.2],[.6,.2],[.3],[.7],[dict(reason='unreviewed_box')])
            self.assertTrue(result['comparison_advance']);self.assertFalse(result['full_surface_quality_met'])
            self.assertEqual(result['sides']['front']['delta_pp']['fn_rate'],-100)
            bad=P.compare(rows,points,[.4,.2],[.6,.8],[.3],[.7],[]);self.assertFalse(bad['comparison_advance'])
            maps=dict(baseline=torch.full((2,256),.4),candidate=torch.full((2,256),.6))
            self.assertEqual(P.render(root,rows,points,torch.ones((2,256),dtype=torch.bool),maps,[.4,.2],[.6,.2],[.3],[.7],result,35,'synthetic'),2)
            self.assertIn('front &amp; positive',(root/'index.html').read_text());self.assertEqual(len(list((root/'images').glob('*.png'))),2)
