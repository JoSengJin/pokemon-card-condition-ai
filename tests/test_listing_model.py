import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.listing_model import ListingAnalyzer, photo_request
from card_condition.regions import REGION_LABELS, region_box


class ListingModelTest(unittest.TestCase):
    def test_masks_missing_review_glare_and_missing_faces_without_truth(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder)/'photo.png'
            image.write_bytes(b'fixture')
            with patch('card_condition.listing_model.RegionAnalyzer') as cls:
                region = cls.return_value
                region.meta = dict(supported=['edge_defect'], architecture='fixture')
                region.model_sha256 = 'frozen'; region.image_size = 224; region.device = 'cpu'
                region.analyze.side_effect = lambda image, box, area, **kw: dict(
                    box=region_box(box, area), probabilities={key: .1 if key == 'edge_defect' else None for key in REGION_LABELS})
                region.analyze_regions.side_effect=lambda image,box,areas,**kw:[region.analyze(image,box,area,**kw) for area in areas]
                analyzer = ListingAnalyzer('model.pt', 'cpu')
                request = dict(id='one', front=dict(image=str(image), box=[0,0,1,1]))
                original = copy.deepcopy(request)
                result = analyzer.analyze(request)
                self.assertEqual(original, request)
                self.assertEqual(0, result['inferred_regions'])
                self.assertEqual(['front'], result['observation_unreviewed_sides'])
                cells = result['listing_readiness']['records'][0]['cells']
                self.assertEqual({'observation_not_reviewed'}, {c['reason'] for c in cells if c['side']=='front'})
                self.assertEqual({'missing_photo'}, {c['reason'] for c in cells if c['side']=='back'})
                request['front']['visibility_issues'] = []
                request['back'] = dict(image=str(image), box=[0,0,1,1], visibility_issues=['glare'], glare_areas=['lower_right'])
                result = analyzer.analyze(request, batch_views=True)
                self.assertEqual(15, result['inferred_regions'])
                cells = result['listing_readiness']['records'][0]['cells']
                limited = [c for c in cells if c['side']=='back' and c['area']=='lower_right']
                self.assertTrue(all(c['reason']=='observation_limited' and c['score'] is None for c in limited))
                self.assertTrue(result['requires_gemini'])
                self.assertFalse(result['training_performed'])
                self.assertFalse(result['same_object_verified'])
                self.assertEqual(0, result['actual_calls_saved'])
                self.assertEqual(1, cls.call_count)
                request['back']['visibility_issues']=['blur']; request['back']['glare_areas']=[]
                self.assertEqual(8,analyzer.analyze(request)['inferred_regions'])
                request['front']['box']=None
                result=analyzer.analyze(request)
                self.assertEqual(0,result['inferred_regions'])
                self.assertIn('missing_card_region',{c['reason'] for c in result['listing_readiness']['records'][0]['cells']})
                json.dumps(result,allow_nan=False)
                request['front']['box']=[0,0,1,1]
                def mutate(image_path,box,area,**kw):
                    image.write_bytes(b'changed')
                    return dict(box=region_box(box,area), probabilities={key: None for key in REGION_LABELS})
                region.analyze.side_effect=mutate
                with self.assertRaisesRegex(ValueError,'inputs changed'):
                    analyzer.analyze(request)

    def test_reject_invalid_contract_before_inference(self):
        valid=dict(id='one',front=dict(image='/absolute/photo.png',box=[0,0,1,1],visibility_issues=[]))
        invalid=[None,[],dict(id=''),dict(id='one',split='train'),dict(id='one',front='bad')]
        for change in (dict(image='relative.png'),dict(box=[0,0,0,1]),dict(visibility_issues=None),
                       dict(visibility_issues=['made_up']),dict(glare_areas=['lower_right']),dict(labels={})):
            candidate=copy.deepcopy(valid);candidate['front'].update(change);invalid.append(candidate)
        for candidate in invalid:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                photo_request(candidate)
        with patch('card_condition.listing_model.RegionAnalyzer'):
            analyzer=ListingAnalyzer('unused')
            with self.assertRaisesRegex(ValueError,'boolean'):
                analyzer.analyze(valid,batch_views=1)
            with self.assertRaises(FileNotFoundError):
                analyzer.analyze(valid)

    def test_observation_reuse_does_not_override_unknown_or_human_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'photo.png';image.write_bytes(b'fixture')
            with patch('card_condition.listing_model.RegionAnalyzer') as region_cls, \
                    patch('card_condition.listing_model.VisibilityAnalyzer') as obs_cls:
                region=region_cls.return_value
                region.meta=dict(supported=['edge_defect'],architecture='fixture')
                region.model_sha256='region';region.image_size=224;region.device='cpu'
                region.analyze.side_effect=lambda image,box,area,**kw:dict(
                    box=region_box(box,area),probabilities={key:.1 if key=='edge_defect' else None for key in REGION_LABELS})
                region.analyze_regions.side_effect=lambda image,box,areas,**kw:[region.analyze(image,box,area,**kw) for area in areas]
                observation=obs_cls.return_value;observation.model_sha256='observation'
                observation.analyze.side_effect=lambda image,box,side:dict(observation_limit_score=.99 if side=='front' else .01)
                request=dict(id='one',front=dict(image=str(image),box=[0,0,1,1]),
                    back=dict(image=str(image),box=[0,0,1,1],visibility_issues=['glare'],glare_areas=['lower_right']))
                plain=ListingAnalyzer('region').analyze(request)
                analyzer=ListingAnalyzer('region',observation_checkpoint='observation')
                for _ in range(2):
                    result=analyzer.analyze(request)
                    self.assertEqual(plain['predictions'],result['predictions'])
                    self.assertEqual(plain['listing_readiness'],result['listing_readiness'])
                    evidence=result['observation_evidence'];self.assertEqual(2,evidence['inferred_faces'])
                    self.assertIsNone(evidence['records'][0]['human_visibility_issues'])
                    self.assertEqual(['glare'],evidence['records'][1]['human_visibility_issues'])
                    self.assertFalse(evidence['routing_changed']);self.assertEqual(0,result['actual_calls_saved'])
                self.assertEqual(1,obs_cls.call_count)
                self.assertEqual(['front','back']*2,[call.kwargs['side'] for call in observation.analyze.call_args_list])
                request['back']['box']=None
                request['back']['glare_areas']=[]
                result=analyzer.analyze(request)
                self.assertEqual('missing_card_region',result['observation_evidence']['records'][1]['reason'])
                del request['back']
                self.assertEqual('missing_photo',analyzer.analyze(request)['observation_evidence']['records'][1]['reason'])
                observation.analyze.side_effect=None
                for value in (float('nan'),float('inf'),-.1,1.1):
                    observation.analyze.return_value=dict(observation_limit_score=value)
                    with self.assertRaisesRegex(ValueError,'Invalid observation score'):
                        analyzer.analyze(request)
                def race(image_path,box,side):
                    image.write_bytes(b'changed-in-observation')
                    return dict(observation_limit_score=.1)
                observation.analyze.side_effect=race
                with self.assertRaisesRegex(ValueError,'inputs changed'):
                    analyzer.analyze(request)
