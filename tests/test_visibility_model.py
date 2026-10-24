import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from card_condition.data import LABELS
from card_condition.visibility_model import TARGET, VisibilityAnalyzer, class_group_weights, experiment, visibility_rows, fit_centroid
from test_pipeline import fixture


class VisibilityModelTest(unittest.TestCase):
    def setup_data(self, root):
        manifest, rows = fixture(root)
        for i, row in enumerate(rows):
            if row['split'] == 'test':
                row['front'] = row['back'] = 'test-must-not-open.png'
                row['labels'] = 'test-must-not-inspect'
                continue
            row['labels'] = {k: None for k in LABELS}
            row['front'], row['back'] = str(root/row['front']), str(root/row['back'])
            row['side_annotations'] = {}
            for side in ('front', 'back'):
                row['side_annotations'][side] = dict(image=row[side], box=[0,0,1,1],
                    labels={k: None for k in LABELS})
            a = row['side_annotations']['front']
            a['visibility_issues'] = ['glare'] if i % 2 else []
            a['labels']['gradable'] = 0 if i % 2 else 1
            a['labels']['surface_defect'] = 1  # Clear visibility does not mean a clean card.
        manifest.write_text('\n'.join(json.dumps(r) for r in rows))
        return manifest, rows

    def test_truth_is_explicit_and_group_weighting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            selected, skipped = visibility_rows(manifest)
            self.assertEqual([0,1,0,1], [r['labels'][TARGET] for r in selected])
            self.assertEqual(4, len(skipped))
            self.assertTrue(all(r['side'] == 'front' for r in selected))
            a = rows[0]['side_annotations']['back']
            a['visibility_issues'] = []
            a['labels']['gradable'] = 0
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            again, _ = visibility_rows(manifest)
            self.assertEqual(selected, again)
            repeated = [selected[0], selected[0], selected[1]]
            self.assertEqual([.5,.5,1.], class_group_weights(repeated))
            with self.assertRaisesRegex(ValueError, 'Both observation'):
                class_group_weights([selected[0]])
            rows[2]['group'] = rows[0]['group']
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaisesRegex(ValueError, 'across splits'):
                visibility_rows(manifest)

    def test_shadow_is_observation_target_not_condition_label(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            a = rows[0]['side_annotations']['back']
            a['visibility_issues'] = ['shadow']
            before_labels = dict(a['labels'])
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            before = manifest.read_bytes()
            selected, _ = visibility_rows(manifest)
            found = next(r for r in selected if r['card_id'] == '0' and r['side'] == 'back')
            self.assertEqual({TARGET: 1}, found['labels'])
            self.assertEqual(['shadow'], found['visibility_issues'])
            self.assertTrue(all(v is None for v in before_labels.values()))
            self.assertEqual(before, manifest.read_bytes())

    def test_train_load_predict_and_guarded_outputs(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            before = manifest.read_bytes()
            output = root/'experiment'
            report = experiment(manifest, output, epochs=2, device='cpu', pretrained=False)
            self.assertEqual({'clear_faces':1,'limited_faces':1},
                {k:report['counts']['train'][k] for k in ('clear_faces','limited_faces')})
            self.assertEqual(2, sum(report['metrics'].values()))
            self.assertEqual(0, report['actual_calls_saved'])
            self.assertFalse(report['production_ready'])
            analyzer = VisibilityAnalyzer(output/'model.pt', 'cpu')
            for prediction in report['predictions']:
                result = analyzer.analyze(prediction['image'], prediction['box'])
                self.assertAlmostEqual(prediction['probabilities'][TARGET], result['observation_limit_score'], places=6)
                self.assertEqual('review_required', result['decision'])
                self.assertTrue(result['requires_gemini'])
            self.assertFalse(any(p.requires_grad for p in analyzer.backbone.parameters()))
            self.assertEqual(before, manifest.read_bytes())
            with self.assertRaisesRegex(ValueError,'Output exists'):
                experiment(manifest, output, device='cpu', pretrained=False)
            with self.assertRaisesRegex(ValueError,'normalized card box'):
                analyzer.analyze(rows[2]['front'], [1,0,0,1])
            with torch.no_grad(): analyzer.head.bias.fill_(float('nan'))
            with self.assertRaisesRegex(ValueError,'Non-finite'):
                analyzer.analyze(rows[2]['front'], [0,0,1,1])
            meta = torch.load(output/'model.pt',weights_only=True)
            meta['image_size'] = 448
            torch.save(meta, root/'invalid.pt')
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                VisibilityAnalyzer(root/'invalid.pt','cpu')

    def test_tiles_bag_checkpoint_roundtrip_and_policy_validation(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            before = manifest.read_bytes()
            result = experiment(manifest, root/'tiles', epochs=2, device='cpu', pretrained=False, tiles=True)
            self.assertEqual('tiles', result['input_policy'])
            self.assertEqual(5, result['views'])
            self.assertEqual(2, result['counts']['train']['faces'])
            analyzer = VisibilityAnalyzer(root/'tiles/model.pt', 'cpu')
            for row in result['predictions']:
                actual = analyzer.analyze(row['image'], row['box'])
                self.assertAlmostEqual(row['probabilities'][TARGET], actual['observation_limit_score'], places=6)
                self.assertEqual('review_required', actual['decision'])
            self.assertEqual(before, manifest.read_bytes())
            meta = torch.load(root/'tiles/model.pt', weights_only=True)
            self.assertEqual(1152, meta['head']['weight'].shape[1])
            meta['input_policy'] = 'human-selected-tile'
            torch.save(meta, root/'invalid-policy.pt')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                VisibilityAnalyzer(root/'invalid-policy.pt', 'cpu')

    def test_weighted_centroid_distance_and_roundtrip(self):
        torch.set_num_threads(1)
        head = torch.nn.Linear(2, 1)
        x = torch.tensor([[0.,0.],[2.,0.],[4.,2.]])
        y = torch.tensor([0.,0.,1.])
        weights = torch.tensor([.75,.25,1.])
        fit_centroid(head,x,y,weights)
        probes = torch.tensor([[1.,1.],[3.,2.]])
        expected = ((probes-torch.tensor([.5,0.])).square().mean(1)
                    - (probes-torch.tensor([4.,2.])).square().mean(1))
        torch.testing.assert_close(head(probes).squeeze(1),expected)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            report = experiment(manifest,root/'centroid',device='cpu',pretrained=False,centroid=True)
            self.assertIsNone(report['selected_epoch'])
            self.assertEqual(0,report['epochs'])
            analyzer = VisibilityAnalyzer(root/'centroid/model.pt','cpu')
            original = {k:v.clone() for k,v in analyzer.head.state_dict().items()}
            for row in report['predictions']:
                actual = analyzer.analyze(row['image'],row['box'])
                self.assertAlmostEqual(actual['observation_limit_score'],row['probabilities'][TARGET],places=6)
            # Swapping only validation truth must not change any learned parameter.
            for row in rows:
                if row['split'] == 'val':
                    a = row['side_annotations']['front']
                    a['visibility_issues'] = [] if a['visibility_issues'] else ['glare']
                    a['labels']['gradable'] = 0 if a['visibility_issues'] else 1
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            experiment(manifest,root/'swapped',device='cpu',pretrained=False,centroid=True)
            changed = VisibilityAnalyzer(root/'swapped/model.pt','cpu')
            for key in original:
                torch.testing.assert_close(original[key],changed.head.state_dict()[key],rtol=0,atol=0)

    def test_interior_preprocessing_saved_and_reproduced(self):
        from card_condition.visibility_model import observation_features
        row = dict(image='unused',box=[.1,.2,.9,.8])
        with patch('card_condition.visibility_model.patch_features') as extract:
            observation_features(None,row,'cpu',interior=True)
            actual = extract.call_args.args[1]['box']
            for found,expected in zip(actual,[.14,.23,.86,.77]):
                self.assertAlmostEqual(expected,found)
        self.assertEqual([.1,.2,.9,.8],row['box'])
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = self.setup_data(root)
            before = manifest.read_bytes()
            report = experiment(manifest,root/'interior',device='cpu',pretrained=False,centroid=True,interior=True)
            self.assertEqual('interior90',report['preprocessing'])
            self.assertEqual(1,report['reason_diagnostics']['glare']['validation_faces'])
            self.assertIsNone(report['reason_diagnostics']['shadow']['recall'])
            analyzer = VisibilityAnalyzer(root/'interior/model.pt','cpu')
            for row in report['predictions']:
                self.assertAlmostEqual(row['probabilities'][TARGET],analyzer.analyze(row['image'],row['box'])['observation_limit_score'],places=6)
            self.assertEqual(before,manifest.read_bytes())
            meta = torch.load(root/'interior/model.pt',weights_only=True)
            meta['preprocessing'] = 'unrecognized'
            torch.save(meta,root/'bad.pt')
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                VisibilityAnalyzer(root/'bad.pt','cpu')

    def test_explicit_front_only_checkpoint_scope_preserves_legacy(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();manifest,rows=self.setup_data(root)
            experiment(manifest,root/'scope-model',device='cpu',pretrained=False,centroid=True)
            path=root/'scope-model/model.pt';meta=torch.load(path,weights_only=True)
            image=rows[0]['front'];box=[0,0,1,1]
            legacy=VisibilityAnalyzer(path,'cpu').analyze(image,box)['observation_limit_score']
            meta['supported_sides']=['front'];torch.save(meta,path)
            scoped=VisibilityAnalyzer(path,'cpu')
            self.assertEqual(legacy,scoped.analyze(image,box,side='front')['observation_limit_score'])
            for side in (None,'back','invalid'):
                with self.assertRaisesRegex(ValueError,'supported observation side'):
                    scoped.analyze(image,box,side=side)
            for value in ([],['front','front'],['unknown'],'front'):
                meta['supported_sides']=value;torch.save(meta,path)
                with self.assertRaisesRegex(ValueError,'side scope'):
                    VisibilityAnalyzer(path,'cpu')
