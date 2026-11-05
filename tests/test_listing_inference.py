import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from card_condition.data import LABELS
from card_condition.listing_inference import infer_listings
from card_condition.regions import REGION_LABELS
from card_condition.side_model import backbone_for
from test_pipeline import fixture


class ListingInferenceTest(unittest.TestCase):
    def test_all_supported_regions_without_label_selection_and_limits(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for row in rows:
                if row['split'] != 'val':
                    row['front'] = row['back'] = 'must-not-open.png'
                    continue
                row['labels'] = {k: None for k in LABELS}
                row['front'], row['back'] = str(root/row['front']), str(root/row['back'])
                row['side_annotations'] = {side: dict(image=row[side], box=[0,0,1,1],
                    labels={k: None for k in LABELS}, visibility_issues=[]) for side in ('front','back')}
            rows[2]['side_annotations']['back'].update(visibility_issues=['glare'], glare_areas=['lower_right'])
            rows[3]['back'] = None
            del rows[3]['side_annotations']['back']
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            backbone, dim = backbone_for('mobilenet_v3_small')
            for policy in ('context', 'tiles'):
                head = torch.nn.Linear(dim*(2 if policy == 'tiles' else 1),3)
                with torch.no_grad():
                    head.weight.zero_(); head.bias.fill_(-3)
                checkpoint = root/(policy+'.pt')
                torch.save(dict(architecture='mobilenet_v3_small_point_'+('edge_tiles_v1' if policy == 'tiles' else 'grid_v1'),
                    backbone_name='mobilenet_v3_small', supported=['edge_defect'], labels=list(REGION_LABELS),
                    backbone=backbone.state_dict(), head=head.state_dict(), edge_input=policy, image_size=224,
                    development_ids=['train'],development_groups=['train'],development_image_hashes=['0'*64]), checkpoint)
                result = infer_listings(manifest, checkpoint, root/(policy+'.json'),'cpu')
                self.assertEqual(23, result['inferred_regions'])
                self.assertEqual(2,result['listing_readiness']['listings'])
                self.assertEqual(0,result['listing_readiness']['local_complete_candidates'])
                self.assertFalse(result['ground_truth_used_for_region_selection'])
                self.assertFalse(result['training_performed'])
                self.assertEqual(0,result['actual_calls_saved'])
                cells=result['listing_readiness']['records'][0]['cells']
                edge={ (c['side'],c['area']):c for c in cells if c['label']=='edge_defect'}
                self.assertEqual('normal',edge['back','upper_left']['state'])
                self.assertEqual('observation_limited',edge['back','lower_right']['reason'])
                self.assertIsNone(edge['back','lower_right']['score'])
                self.assertNotIn('not_evaluated',{c['reason'] for c in cells})
                self.assertIn('unsupported',{c['reason'] for c in cells})
                self.assertEqual(before,manifest.read_bytes())
                unreviewed=copy.deepcopy(rows)
                del unreviewed[2]['side_annotations']['front']['visibility_issues']
                unknown_manifest=root/(policy+'-unreviewed.jsonl')
                unknown_manifest.write_text('\n'.join(json.dumps(r) for r in unreviewed))
                unknown=infer_listings(unknown_manifest,checkpoint,root/(policy+'-unreviewed.json'),'cpu')
                self.assertEqual(15,unknown['inferred_regions'])
                self.assertFalse(any(p['card_id']==rows[2]['id'] and p['side']=='front'
                    for p in unknown['predictions']))
                front_cells=[c for c in unknown['listing_readiness']['records'][0]['cells']
                             if c['side']=='front']
                self.assertTrue(all(c['state']=='unknown' and c['score'] is None and
                    c['reason']=='observation_not_reviewed' for c in front_cells))
                batched=infer_listings(manifest,checkpoint,root/(policy+'-batched.json'),
                    'cpu',batch_views=True)
                self.assertEqual(result['predictions'],batched['predictions'])
                self.assertEqual(result['listing_readiness'],batched['listing_readiness'])
                self.assertTrue(batched['batched_views'])
                self.assertNotIn('memory_profile',batched)
                failed_output=root/(policy+'-memory-failure.json')
                original_batched=__import__('card_condition.edge_views',fromlist=['batched_patch_features']).batched_patch_features
                calls=[]
                def fail_second(*args,**kwargs):
                    calls.append(1)
                    if len(calls)==2:
                        raise torch.OutOfMemoryError('simulated batch allocation failure')
                    return original_batched(*args,**kwargs)
                with patch('card_condition.edge_views.batched_patch_features',side_effect=fail_second):
                    with self.assertRaises(torch.OutOfMemoryError):
                        infer_listings(manifest,checkpoint,failed_output,'cpu',batch_views=True)
                self.assertEqual(2,len(calls))
                self.assertFalse(failed_output.exists())
                recovered=infer_listings(manifest,checkpoint,failed_output,'cpu')
                self.assertEqual(result['predictions'],recovered['predictions'])
                self.assertTrue(recovered['requires_gemini'])
                self.assertEqual(0,recovered['actual_calls_saved'])
                with self.assertRaisesRegex(ValueError,'MPS only'):
                    infer_listings(manifest,checkpoint,root/(policy+'-cpu-profile.json'),
                        'cpu',profile_memory=True)
                self.assertFalse((root/(policy+'-cpu-profile.json')).exists())

                self.assertNotIn('observation_evidence', result)
                observation_checkpoint=root/'observation.pt'
                observation_checkpoint.write_bytes(b'frozen-observation-fixture')
                with patch('card_condition.listing_observation.VisibilityAnalyzer') as analyzer:
                    analyzer.return_value.model_sha256=hashlib.sha256(observation_checkpoint.read_bytes()).hexdigest()
                    analyzer.return_value.analyze.side_effect=lambda image, box, side: dict(
                        observation_limit_score=.01 if side=='back' else .99)
                    composed=infer_listings(manifest,checkpoint,root/(policy+'-composed.json'),
                        'cpu',observation_checkpoint)
                    self.assertEqual(3,analyzer.return_value.analyze.call_count)
                    self.assertEqual(['front','back','front'],
                        [call.kwargs['side'] for call in analyzer.return_value.analyze.call_args_list])
                self.assertEqual(result['predictions'],composed['predictions'])
                self.assertEqual(result['listing_readiness'],composed['listing_readiness'])
                evidence=composed['observation_evidence']
                self.assertEqual(3,evidence['inferred_faces'])
                self.assertEqual(['glare'],evidence['records'][1]['human_visibility_issues'])
                self.assertEqual(['lower_right'],evidence['records'][1]['human_glare_areas'])
                self.assertEqual(.01,evidence['records'][1]['observation_limit_score'])
                self.assertEqual('missing_photo',evidence['records'][3]['reason'])
                self.assertIsNone(evidence['records'][3]['observation_limit_score'])
                self.assertFalse(evidence['routing_changed'])
                self.assertEqual(0,composed['actual_calls_saved'])
                with patch('card_condition.listing_observation.VisibilityAnalyzer') as analyzer:
                    analyzer.return_value.model_sha256=hashlib.sha256(observation_checkpoint.read_bytes()).hexdigest()
                    def race(image,box,side):
                        observation_checkpoint.write_bytes(b'changed-during-inference')
                        return dict(observation_limit_score=.5)
                    analyzer.return_value.analyze.side_effect=race
                    with self.assertRaisesRegex(ValueError,'inputs changed'):
                        infer_listings(manifest,checkpoint,root/(policy+'-observation-race.json'),
                            'cpu',observation_checkpoint)
                self.assertFalse((root/(policy+'-observation-race.json')).exists())
                limited = copy.deepcopy(rows)
                limited[2]['side_annotations']['back'].update(
                    visibility_issues=['low_resolution'], glare_areas=[])
                limited_manifest = root/('limited-'+policy+'.jsonl')
                limited_manifest.write_text('\n'.join(json.dumps(r) for r in limited))
                limited_before = limited_manifest.read_bytes()
                held = infer_listings(limited_manifest, checkpoint,
                    root/(policy+'-limited.json'), 'cpu')
                self.assertEqual(16, held['inferred_regions'])
                self.assertFalse(any(p['card_id'] == rows[2]['id'] and p['side'] == 'back'
                                     for p in held['predictions']))
                held_record = held['listing_readiness']['records'][0]
                held_back = [c for c in held_record['cells'] if c['side'] == 'back']
                self.assertTrue(all(c['state'] == 'unknown' and c['score'] is None
                                    and c['reason'] == 'observation_limited' for c in held_back))
                self.assertTrue(held_record['additional_photos_required'])
                self.assertEqual(0, held['actual_calls_saved'])
                self.assertEqual(limited_before, limited_manifest.read_bytes())
                changed=copy.deepcopy(rows)
                changed[2]['side_annotations']['front']['labels']['edge_defect']=1
                changed[2]['side_annotations']['front']['defect_points']=[dict(label='edge_defect',x=.01,y=.01)]
                other=root/('changed-'+policy+'.jsonl')
                other.write_text('\n'.join(json.dumps(r) for r in changed))
                again=infer_listings(other,checkpoint,root/(policy+'-other.json'),'cpu')
                self.assertEqual(result['predictions'],again['predictions'])
                with self.assertRaisesRegex(ValueError,'Output exists'):
                    infer_listings(manifest,checkpoint,root/(policy+'.json'),'cpu')
            original_features = __import__('card_condition.edge_views',fromlist=['patch_features']).patch_features
            def mutate(*args,**kwargs):
                manifest.write_bytes(before+b'\n')
                return original_features(*args,**kwargs)
            with patch('card_condition.edge_views.patch_features',side_effect=mutate):
                with self.assertRaisesRegex(ValueError,'inputs changed'):
                    infer_listings(manifest,checkpoint,root/'race.json','cpu')
            self.assertFalse((root/'race.json').exists())
