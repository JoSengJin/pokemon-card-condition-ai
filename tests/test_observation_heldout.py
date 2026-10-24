import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import torch
import test_visibility_model
from card_condition.data import LABELS
from card_condition.point_probe import digest
from card_condition.visibility_model import experiment
from card_condition.observation_heldout import evaluate_heldout


class HeldoutTest(unittest.TestCase):
    def setup_data(self,root):
        manifest,_=test_visibility_model.VisibilityModelTest().setup_data(root)
        experiment(manifest,root/'model',device='cpu',pretrained=False,centroid=True)
        rows=[]
        for i in range(2):
            row=dict(id='new-'+str(i),group='new-'+str(i),split='test',labels={k:None for k in LABELS},side_annotations={})
            for side in ('front','back'):
                path=root/f'new-{i}-{side}.png'
                Image.new('RGB',(90,130),(230-i*30,180,30 if side=='front' else 60)).save(path)
                row[side]=str(path)
                row['side_annotations'][side]=dict(image=str(path),box=[0,0,1,1],visibility_issues=['glare'] if i else [],
                    labels={k:(1-i if k=='gradable' else None) for k in LABELS})
            rows.append(row)
        rows.append(dict(id='train-not-read',group='train-not-read',split='train',front='bad.png',back='bad.png',labels='invalid'))
        heldout=root/'heldout.jsonl';heldout.write_text('\n'.join(json.dumps(r) for r in rows))
        checkpoint=root/'model/model.pt'
        return checkpoint,heldout,rows

    def test_frozen_prediction_only_and_source_preserved(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();checkpoint,manifest,rows=self.setup_data(root)
            before=(digest(checkpoint),manifest.read_bytes())
            with patch('card_condition.visibility_model.fit_centroid',side_effect=AssertionError('must not fit')):
                report=evaluate_heldout(checkpoint,manifest,root/'report',digest(checkpoint),'cpu')
            self.assertEqual('test',report['split'])
            self.assertEqual(4,report['summary']['faces'])
            self.assertFalse(report['fitted_model'])
            self.assertFalse(report['selected_model'])
            self.assertFalse(report['development_overlap'])
            self.assertTrue(all(r['split']=='test' for r in report['predictions']))
            self.assertEqual(before,(digest(checkpoint),manifest.read_bytes()))
            with self.assertRaisesRegex(ValueError,'Output exists'):
                evaluate_heldout(checkpoint,manifest,root/'report',digest(checkpoint),'cpu')
            with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
                evaluate_heldout(checkpoint,manifest,root/'wrong','0'*64,'cpu')

    def test_physical_group_rates_do_not_overweight_multiple_faces(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();checkpoint,manifest,rows=self.setup_data(root)
            # One clear physical card has two faces; a second clear card has one.
            third=copy.deepcopy(rows[1]);third.update(id='third',group='third',back=None)
            third['side_annotations']={'front':copy.deepcopy(rows[0]['side_annotations']['front'])}
            image=root/'third.png';Image.new('RGB',(90,130),(20,90,170)).save(image)
            third['front']=str(image);third['side_annotations']['front']['image']=str(image)
            manifest.write_text('\n'.join(json.dumps(r) for r in rows+[third]))
            scores=iter([.9,.9,.1,.1,.1])
            with patch('card_condition.observation_heldout.VisibilityAnalyzer') as model:
                model.return_value.analyze.side_effect=lambda *a,**kw:dict(observation_limit_score=next(scores))
                report=evaluate_heldout(checkpoint,manifest,root/'report',digest(checkpoint),'cpu')
            self.assertEqual(2,report['by_group']['new-0']['observation_limited']['fp'])
            rates=report['group_error_rates_at_05']['observation_limited']
            self.assertEqual(2,rates['negative_groups'])
            self.assertEqual(1,rates['positive_groups'])
            self.assertEqual(.5,rates['mean_false_positive_rate'])
            self.assertEqual(1.,rates['mean_miss_rate'])
            self.assertAlmostEqual(2/3,report['summary']['rates_at_05']['false_positive_rate'])

    def test_development_group_id_and_copied_pixels_are_rejected(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();checkpoint,manifest,rows=self.setup_data(root)
            for key in ('group','id'):
                changed=copy.deepcopy(rows);changed[0][key]='0'
                manifest.write_text('\n'.join(json.dumps(r) for r in changed))
                with self.assertRaisesRegex(ValueError,'used in development'):
                    evaluate_heldout(checkpoint,manifest,root/'out',digest(checkpoint),'cpu')
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            Image.open(root/'0-front.png').save(rows[0]['front'])
            with self.assertRaisesRegex(ValueError,'pixels were used'):
                evaluate_heldout(checkpoint,manifest,root/'out',digest(checkpoint),'cpu')
            self.assertFalse((root/'out').exists())

    def test_unknown_truth_and_missing_provenance_do_not_produce_results(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();checkpoint,manifest,rows=self.setup_data(root)
            for row in rows[:2]:
                for a in row['side_annotations'].values():
                    a['visibility_issues']=[];a['labels']['gradable']=None
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError,'No explicit'):
                evaluate_heldout(checkpoint,manifest,root/'out',digest(checkpoint),'cpu')
            meta=torch.load(checkpoint,weights_only=True);del meta['development_groups']
            torch.save(meta,root/'invalid.pt')
            with self.assertRaisesRegex(ValueError,'provenance'):
                evaluate_heldout(root/'invalid.pt',manifest,root/'out',digest(root/'invalid.pt'),'cpu')
            self.assertFalse((root/'out').exists())

    def test_test_groups_with_identical_pixels_are_not_independent_samples(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();checkpoint,manifest,rows=self.setup_data(root)
            Image.open(rows[0]['front']).save(rows[1]['front'])
            with self.assertRaisesRegex(ValueError,'different physical groups'):
                evaluate_heldout(checkpoint,manifest,root/'out',digest(checkpoint),'cpu')
            self.assertFalse((root/'out').exists())

    def test_malformed_provenance_is_rejected_before_inference(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            checkpoint,manifest,rows=self.setup_data(root)
            original=torch.load(checkpoint,weights_only=True)
            for key in ('development_ids','development_groups','development_image_hashes'):
                invalid=[[],[''],['  '],[None],'invalid']
                if key=='development_image_hashes':
                    invalid += [['short'],['z'*64]]
                for value in invalid:
                    with self.subTest(key=key,value=value):
                        torch.save(dict(original,**{key:value}),checkpoint)
                        with patch('card_condition.observation_heldout.VisibilityAnalyzer',
                                   side_effect=AssertionError('must reject before inference')) as create:
                            with self.assertRaisesRegex(ValueError,'provenance'):
                                evaluate_heldout(checkpoint,manifest,root/'out',digest(checkpoint),'cpu')
                            create.assert_not_called()
                        self.assertFalse((root/'out').exists())
