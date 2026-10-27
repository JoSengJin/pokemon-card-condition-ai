import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from card_condition.listing_model import ListingAnalyzer
from card_condition.listing_coverage import assess_coverage
from card_condition.regions import GLARE_AREAS, REGION_LABELS, REGION_TARGET_AREAS, region_box
from test_release import fixture_release


def pin_bundle(root, included=True):
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    case = dict(id='one', request=dict(path='request.json', sha256=digest(root/'request.json')),
                report=dict(path='report.json', sha256=digest(root/'report.json')))
    value = dict(schema_version=1, manifest_sha256=digest(root/'truth.jsonl'),
                 release_sha256=digest(root/'release.json'), cases=[case] if included else [])
    (root/'bundle.json').write_text(json.dumps(value))
    return digest(root/'bundle.json')


def scenario(root):
    release, checkpoint = fixture_release(root)
    request = json.loads((root/'request.json').read_text())
    labels = dict(gradable=None, centering_defect=0, corner_defect=0, edge_defect=0, surface_defect=0)
    source = dict(id='one', group='physical-one', split='val', front=request['front']['image'], back=None,
                  labels=labels, side_annotations=dict(front=dict(image=request['front']['image'], box=request['front']['box'],
                      box_reviewed=True, visibility_issues=[], labels=labels,
                      region_labels={area: {q: 0 if area in REGION_TARGET_AREAS[q] else None for q in REGION_LABELS}
                                     for area in GLARE_AREAS})))
    region = Mock(meta=dict(supported=['surface_defect'], architecture='mobilenet_v3_small_region_v1'),
                  model_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(), image_size=224, device='cpu')
    region.analyze.side_effect = lambda image, box, area, **kw: dict(box=region_box(box,area),
        probabilities=dict(corner_defect=None,edge_defect=None,surface_defect=.1))
    with patch('card_condition.listing_model.RegionAnalyzer', return_value=region):
        analyzer = ListingAnalyzer(release=release, device='cpu')
    report = analyzer.analyze(request)
    (root/'truth.jsonl').write_text(json.dumps(source))
    (root/'report.json').write_text(json.dumps(report))
    return source, request, report, analyzer


class ListingCoverageTest(unittest.TestCase):
    def test_saved_producer_output_missing_report_and_missing_request_keep_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, request, report, analyzer = scenario(root)
            sha = pin_bundle(root)
            with patch('card_condition.listing_model.RegionAnalyzer', side_effect=AssertionError('No model loading/inference')):
                result = assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,root/'ok.json')
            self.assertEqual((46,23,9,14),(result['required_cells'],result['known_observable_cells'],result['nondeferred_cells'],result['deferred_cells']))
            self.assertAlmostEqual(9/23,result['coverage'])
            self.assertEqual(12,result['hold_reasons']['unsupported'])
            self.assertFalse(result['numeric_condition_met'] or result['e2_verified'] or result['production_ready'])
            sha = pin_bundle(root,False)
            missing = assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,root/'missing.json')
            self.assertEqual((23,0),(missing['known_observable_cells'],missing['nondeferred_cells']))
            self.assertEqual(['one'],missing['missing_reports'])
            request = dict(id='one')
            (root/'request.json').write_text(json.dumps(request))
            (root/'report.json').write_text(json.dumps(analyzer.analyze(request)))
            sha = pin_bundle(root)
            absent = assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,root/'absent.json')
            self.assertEqual((23,0),(absent['known_observable_cells'],absent['nondeferred_cells']))
            self.assertEqual(21,absent['hold_reasons']['missing_photo'])

    def test_unknown_truth_glare_and_unreviewed_geometry_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            original, request, report, analyzer = scenario(root)
            for change in ('unknown','whole_normal','glare','unreviewed','threshold'):
                source,req = copy.deepcopy(original),copy.deepcopy(request)
                face = source['side_annotations']['front']
                if change=='unknown':
                    face['region_labels']['center']['surface_defect']=None
                    expected=(22,8)
                elif change=='whole_normal':
                    face['region_labels']={}
                    expected=(2,0)
                elif change=='glare':
                    face.update(visibility_issues=['glare'],glare_areas=['center'])
                    req['front'].update(visibility_issues=['glare'],glare_areas=['center'])
                    expected=(20,8)
                elif change=='threshold':
                    face['region_labels']['upper_left']['surface_defect']=None
                    for values in face['region_labels'].values():
                        values['corner_defect']=None;values['edge_defect']=None
                    analyzer.region.analyze.side_effect=lambda image, box, area, **kw: dict(box=region_box(box,area),
                        probabilities=dict(corner_defect=None,edge_defect=None,surface_defect=.5 if area=='center' else .1))
                    expected=(10,7)
                else:
                    face['box_reviewed']=False
                    expected=(0,0)
                (root/'truth.jsonl').write_text(json.dumps(source))
                (root/'request.json').write_text(json.dumps(req))
                (root/'report.json').write_text(json.dumps(analyzer.analyze(req)))
                sha = pin_bundle(root)
                with self.subTest(change=change):
                    result = assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,root/(change+'.json'))
                    self.assertEqual(expected,(result['known_observable_cells'],result['nondeferred_cells']))
                    if change=='threshold':
                        self.assertEqual(.7,result['coverage'])
                        self.assertTrue(result['numeric_condition_met'])
                        self.assertFalse(result['e2_verified'])
                    if change=='unreviewed':
                        self.assertIsNone(result['coverage'])
                        self.assertFalse(result['numeric_condition_met'])

    def test_tampered_geometry_policy_score_release_and_pin_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, request, report, _ = scenario(root)
            for change in ('geometry','state','score','unsupported','release','architecture','auxiliary','pin'):
                req,value = copy.deepcopy(request),copy.deepcopy(report)
                if change=='geometry':req['front']['box']=[0,0,1,1]
                elif change=='state':value['listing_readiness']['records'][0]['cells'][0]['state']='normal'
                elif change=='score':value['predictions'][0]['probabilities']['surface_defect']=float('nan')
                elif change=='unsupported':value['predictions'][0]['probabilities']['corner_defect']=.1
                elif change=='release':value['release']['release_id']='other'
                elif change=='architecture':value['architecture']='other'
                elif change=='auxiliary':value['observation_evidence']=dict(model_sha256='0'*64)
                (root/'request.json').write_text(json.dumps(req))
                (root/'report.json').write_text(json.dumps(value))
                sha = pin_bundle(root)
                if change=='pin':(root/'report.json').write_text(json.dumps(dict(value,device='other')))
                output=root/('rejected-'+change+'.json')
                with self.subTest(change=change),self.assertRaises(ValueError):
                    assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,output)
                self.assertFalse(output.exists())

    def test_alias_photos_train_mixed_split_and_duplicate_cases_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, request, report, _ = scenario(root)
            for change in ('alias','train','mixed','duplicate'):
                first=copy.deepcopy(source)
                if change=='alias':
                    other=copy.deepcopy(source);other['id']='alias'
                    text=json.dumps(first)+'\n'+json.dumps(other)
                elif change=='train':
                    first['split']='train';text=json.dumps(first)
                elif change=='mixed':
                    other=copy.deepcopy(source);other.update(id='other',group='other',split='test')
                    text=json.dumps(first)+'\n'+json.dumps(other)
                else:text=json.dumps(first)
                (root/'truth.jsonl').write_text(text)
                sha=pin_bundle(root)
                if change=='duplicate':
                    bundle=json.loads((root/'bundle.json').read_text());bundle['cases']*=2
                    (root/'bundle.json').write_text(json.dumps(bundle))
                    sha=hashlib.sha256((root/'bundle.json').read_bytes()).hexdigest()
                with self.subTest(change=change),self.assertRaises(ValueError):
                    assess_coverage(root/'truth.jsonl',root/'release.json',root/'bundle.json',sha,root/(change+'.json'))

    def test_cli_atomic_output_and_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            scenario(root);sha=pin_bundle(root)
            inputs={p:p.read_bytes() for p in root.iterdir()}
            cmd=[sys.executable,'-m','card_condition.listing_coverage',str(root/'truth.jsonl'),str(root/'release.json'),
                 str(root/'bundle.json'),str(root/'cli.json'),'--bundle-sha256',sha]
            run=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(0,run.returncode,run.stderr)
            self.assertEqual(23,json.loads(run.stdout)['known_observable_cells'])
            before=(root/'cli.json').read_bytes()
            run=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(1,run.returncode)
            self.assertEqual(before,(root/'cli.json').read_bytes())
            self.assertTrue(all(p.read_bytes()==raw for p,raw in inputs.items()))
