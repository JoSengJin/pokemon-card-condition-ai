import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import torch
from card_condition.data import LABELS
from card_condition.regions import REGION_LABELS
from card_condition.point_probe import digest
from card_condition import region_evaluation, side_evaluation
from test_pipeline import fixture


def evaluation_fixture(root, kind):
    _,rows=fixture(root)
    for row in rows:
        for side in ('front','back'):row[side]=str(root/row[side])
        row['side_annotations']={side:dict(image=row[side],box=[0,0,1,1],labels=dict(row['labels']),
            region_labels={'upper_left':{k:row['labels'][k] if k=='corner_defect' else None for k in REGION_LABELS}})
            for side in ('front','back')}
    manifest=root/'test.jsonl';manifest.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
    history=root/'history.jsonl';history.write_text('\n'.join(json.dumps(r) for r in rows[:4]))
    meta=dict(development_ids=[r['id'] for r in rows[:4]],
        development_groups=[r['group'] for r in rows[:4]],training_groups=[r['group'] for r in rows[:4]],
        development_image_hashes=['0'*64],
        supported=['corner_defect'] if kind=='region' else list(LABELS),
        labels=list(LABELS),architecture='mobilenet_v3_small_single_side_v1',crop=True)
    checkpoint=root/'model.pt';torch.save(meta,checkpoint)
    analyzer=Mock(model_sha256=digest(checkpoint))
    analyzer.analyze.return_value=dict(probabilities={k:.8 if k=='corner_defect' else None for k in REGION_LABELS},null_reasons={})
    analyzer.predict.return_value={k:.8 for k in LABELS}
    return manifest,history,checkpoint,rows,analyzer


def evaluate(kind, module, manifest,history,checkpoint,output):
    if kind=='region':return module.evaluate_regions(manifest,checkpoint,output,[history],'cpu')
    return module.evaluate_sides(manifest,checkpoint,output,'final',[history],'cpu')


class EvaluationInputsTest(unittest.TestCase):
    def test_normal_provenance_and_denominators(self):
        for kind,module,constructor in (('region',region_evaluation,'RegionAnalyzer'),('side',side_evaluation,'SideAnalyzer')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root=Path(folder).resolve();manifest,history,checkpoint,rows,analyzer=evaluation_fixture(root,kind)
                with patch.object(module,constructor,return_value=analyzer):
                    report=evaluate(kind,module,manifest,history,checkpoint,root/'out.json')
                self.assertEqual(4,report['rates_at_05']['corner_defect']['scored'])
                self.assertEqual(.5,report['rates_at_05']['corner_defect']['accuracy'])
                self.assertEqual(digest(checkpoint),report['model_sha256'])
                self.assertTrue(all(digest(p)==v for p,v in report['input_hashes'].items()))
                self.assertFalse(report['production_ready'])

    def test_copied_pixels_are_not_new_physical_groups(self):
        for kind,module,constructor in (('region',region_evaluation,'RegionAnalyzer'),('side',side_evaluation,'SideAnalyzer')):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                root=Path(folder).resolve();manifest,history,checkpoint,rows,analyzer=evaluation_fixture(root,kind)
                Image.open(rows[4]['front']).save(rows[5]['front'])
                with patch.object(module,constructor,return_value=analyzer) as loader:
                    with self.assertRaisesRegex(ValueError,'different physical groups'):
                        evaluate(kind,module,manifest,history,checkpoint,root/'out.json')
                    loader.assert_not_called()
                self.assertFalse((root/'out.json').exists())

    def test_input_mutation_never_saves_success(self):
        for kind,module,constructor in (('region',region_evaluation,'RegionAnalyzer'),('side',side_evaluation,'SideAnalyzer')):
            for target in ('photo','model','manifest','history'):
                with self.subTest(kind=kind,target=target),tempfile.TemporaryDirectory() as folder:
                    root=Path(folder).resolve();manifest,history,checkpoint,rows,analyzer=evaluation_fixture(root,kind)
                    path={'photo':Path(rows[4]['front']),'model':checkpoint,'manifest':manifest,'history':history}[target]
                    original=path.read_bytes();method=analyzer.analyze if kind=='region' else analyzer.predict
                    answer=method.return_value
                    def changed(*args,**kwargs):
                        path.write_bytes(original+b' ')
                        return answer
                    method.side_effect=changed
                    with patch.object(module,constructor,return_value=analyzer):
                        with self.assertRaisesRegex(ValueError,'inputs changed'):
                            evaluate(kind,module,manifest,history,checkpoint,root/'out.json')
                    self.assertFalse((root/'out.json').exists())

    def test_physical_card_rates_do_not_weight_cards_by_region_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,history,checkpoint,rows,analyzer=evaluation_fixture(root,'region')
            rows[5]['side_annotations']['back']['labels']['corner_defect']=0
            rows[5]['side_annotations']['back']['region_labels']['upper_left']['corner_defect']=0
            manifest.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
            def prediction(image, *args):
                return dict(probabilities={k:(.2 if image==rows[4]['front'] else .8)
                    if k=='corner_defect' else None for k in REGION_LABELS},null_reasons={})
            analyzer.analyze.side_effect=prediction
            with patch.object(region_evaluation,'RegionAnalyzer',return_value=analyzer):
                report=region_evaluation.evaluate_regions(manifest,checkpoint,root/'out.json',[history],'cpu')
            pooled=report['rates_at_05']['corner_defect']
            groups=report['group_error_rates_at_05']['corner_defect']
            self.assertAlmostEqual(2/3,pooled['false_positive_rate'])
            self.assertEqual(.75,groups['mean_false_positive_rate'])
            self.assertEqual(2,groups['negative_groups'])
            self.assertEqual(1,groups['positive_groups'])
            self.assertEqual(0,groups['mean_miss_rate'])

    def test_malformed_development_provenance_is_rejected(self):
        for kind,module,constructor,group_key in (
                ('region',region_evaluation,'RegionAnalyzer','development_groups'),
                ('side',side_evaluation,'SideAnalyzer','training_groups')):
            for key in (group_key,'development_ids','development_image_hashes'):
                invalid = ([], '', [''], [None], {'unexpected':'value'}, None)
                if key == 'development_image_hashes':
                    invalid += (['z'*64], ['abc'])
                for value in invalid:
                    with self.subTest(kind=kind,key=key,value=value),tempfile.TemporaryDirectory() as folder:
                        root=Path(folder).resolve()
                        manifest,history,checkpoint,rows,analyzer=evaluation_fixture(root,kind)
                        meta=torch.load(checkpoint,weights_only=True);meta[key]=value;torch.save(meta,checkpoint)
                        output=root/'out.json'
                        with patch.object(module,constructor,return_value=analyzer) as loader:
                            with self.assertRaisesRegex(ValueError,'development provenance'):
                                evaluate(kind,module,manifest,history,checkpoint,output)
                            loader.assert_not_called()
                        self.assertFalse(output.exists())
