import json
from pathlib import Path
import tempfile
import unittest
import torch
from PIL import Image
from test_pipeline import fixture
from card_condition.side_experiment import experiment, side_rows, side_tensor, side_views, visibility_report

class SideExperimentTest(unittest.TestCase):
    def test_glare_slices_preserve_unknown_and_ignore_test(self):
        rows = [{'id':'train/front','split':'train','visibility_issues':['glare'],'glare_areas':[],
                 'labels':{k:0 for k in ('gradable','surface_defect')}},
                {'id':'val/back','split':'val','visibility_issues':['glare'],'glare_areas':['lower_right'],
                 'labels':{'gradable':0,'surface_defect':None}},
                {'id':'test/back','split':'test','visibility_issues':['glare'],'glare_areas':['center'],
                 'labels':{'gradable':1,'surface_defect':1}}]
        report=visibility_report(rows, [[.9,0,0,0,.1]], ['gradable','surface_defect'])
        self.assertEqual({'tp':0,'tn':0,'fp':1,'fn':0},report['glare_area_validation_metrics']['lower_right']['gradable'])
        self.assertEqual(0,sum(report['glare_area_validation_metrics']['lower_right']['surface_defect'].values()))
        self.assertEqual(1,report['glare_area_unknown_labels']['lower_right']['surface_defect'])
        self.assertEqual(['train/front'],report['glare_location_coverage']['train']['unlocated_ids'])
        self.assertNotIn('center',report['glare_area_validation_metrics'])

    def test_crop_training_and_label_isolation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();path,rows=fixture(root)
            for r in rows:
                r['side_annotations']={s:{'image':str(root/r[s]),'box':[.2,.2,.8,.8],
                    'labels':dict(r['labels'])} for s in ('front','back')}
            for r in rows[::2]:
                r['side_annotations']['front']['visibility_issues']=['glare']
            rows[0]['side_annotations']['back']['labels']['edge_defect']=None
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            parsed,_,_=side_rows(path)
            self.assertIsNone(parsed[1]['labels']['edge_defect'])
            for crop,tiles in ((False,False),(True,False),(False,True)):
                report=experiment(path,root/(str(crop)+str(tiles)),crop,device='cpu',epochs=1,pretrained=False,tiles=tiles)
                self.assertEqual({'train':4,'val':4},report['counts'])
                self.assertTrue(report['requires_gemini'])
                self.assertFalse(report['production_ready'])
                self.assertEqual('validation',report['evaluation_kind'])
                self.assertTrue(all(p['id'].startswith(('2/','3/')) for p in report['predictions']))
                self.assertEqual(4,sum(report['metrics']['corner_defect'].values()))
                self.assertEqual(1,report['visibility_counts']['train']['glare'])
                self.assertEqual(1,report['visibility_counts']['val']['glare'])
                self.assertEqual(1,sum(report['visibility_validation_metrics']['glare']['gradable'].values()))
                checkpoint=torch.load(root/(str(crop)+str(tiles))/'model.pt',weights_only=True)
                self.assertEqual(crop,checkpoint['crop'])
                from card_condition.model import ConditionModel
                backbone=ConditionModel().features.eval();backbone.load_state_dict(checkpoint['backbone'])
                head=torch.nn.Linear(576*(5 if tiles else 1),5);head.load_state_dict(checkpoint['head'])
                with torch.inference_mode():
                    restored=head(backbone(side_views(root/'2-front.png',[.2,.2,.8,.8],crop,tiles)).mean((2,3)).flatten().unsqueeze(0)).sigmoid()[0]
                self.assertTrue(torch.allclose(restored,torch.tensor(list(report['predictions'][0]['probabilities'].values())),atol=1e-6))
                with self.assertRaises(ValueError): experiment(path,root/(str(crop)+str(tiles)))
            image=Image.new('RGB',(100,100),'red');image.paste('blue',(20,20,80,80));image.save(root/'crop.png')
            full=side_tensor(root/'crop.png',[.2,.2,.8,.8],False)
            crop=side_tensor(root/'crop.png',[.2,.2,.8,.8],True)
            self.assertFalse(torch.equal(full,crop))
            self.assertEqual((3,224,224),tuple(crop.shape))

    def test_test_images_and_labels_do_not_influence_training(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();path,rows=fixture(root)
            for r in rows:
                r['side_annotations']={s:{'image':str(root/r[s]),'box':[0,0,1,1], 'labels':dict(r['labels'])} for s in ('front','back')}
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            first=experiment(path,root/'first',device='cpu',epochs=1,pretrained=False,tiles=True)
            # Even unreadable test paths and invalid test labels must not enter development.
            for r in rows:
                if r['split']=='test':
                    r['front']='DOES_NOT_EXIST.png';r['labels']={'invalid':'test truth'}
            # Diagnostic locations on training data must not change learned weights.
            rows[0]['side_annotations']['front']['visibility_issues']=['glare']
            rows[0]['side_annotations']['front']['glare_areas']=['lower_right']
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            second=experiment(path,root/'second',device='cpu',epochs=1,pretrained=False,tiles=True)
            self.assertEqual(first['history'],second['history'])
            self.assertEqual(first['predictions'],second['predictions'])
            a=torch.load(root/'first/model.pt',weights_only=True)['head']
            b=torch.load(root/'second/model.pt',weights_only=True)['head']
            self.assertTrue(all(torch.equal(a[k],b[k]) for k in a))

    def test_tiles_cover_four_corners(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quadrants.png'
            image=Image.new('RGB',(100,100),'red')
            image.paste('green',(50,0,100,50));image.paste('blue',(0,50,50,100));image.paste('white',(50,50,100,100));image.save(path)
            views=side_views(path,[0,0,1,1],tiles=True)
            self.assertEqual((5,3,224,224),tuple(views.shape))
            for i,(x,y) in enumerate(((0,0),(99,0),(0,99),(99,99)),1):
                pixel=views[i,:,-1 if y else 0,-1 if x else 0]
                expected=(torch.tensor(image.getpixel((x,y)))/255-torch.tensor([.485,.456,.406]))/torch.tensor([.229,.224,.225])
                self.assertTrue(torch.allclose(pixel,expected,atol=1e-6))
