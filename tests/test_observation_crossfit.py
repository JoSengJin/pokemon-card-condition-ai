import json
from pathlib import Path
import tempfile
import unittest
import torch
import test_visibility_model
from card_condition.observation_crossfit import group_crossfit,reject_duplicate_groups
from card_condition.visibility_model import TARGET


class ObservationCrossfitTest(unittest.TestCase):
    def test_excludes_whole_group_and_does_not_read_validation_or_test(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,rows=test_visibility_model.VisibilityModelTest().setup_data(root)
            for i,row in enumerate(rows):
                if row['split']=='test':continue
                row['split']='train'
                a=row['side_annotations']['back'];a['visibility_issues']=[] if i%2 else ['glare']
                a['labels']['gradable']=1 if i%2 else 0
            rows.append(dict(id='val-not-read',group='val-not-read',split='val',front='bad.png',back='bad.png',labels='invalid'))
            manifest.write_text('\n'.join(json.dumps(r) for r in rows));before=manifest.read_bytes()
            report=group_crossfit(manifest,root/'first',device='cpu',pretrained=False,compare_ridge=True,compare_context=True,compare_logistic=True,compare_glare_only=True)
            self.assertEqual(before,manifest.read_bytes())
            self.assertEqual('train',report['split'])
            self.assertEqual(4,len(report['folds']))
            self.assertEqual(8,report['summaries']['global']['faces'])
            self.assertFalse(report['refused_folds'])
            self.assertEqual(1.0,report['ridge_comparison']['penalty'])
            self.assertFalse(report['ridge_comparison']['hyperparameter_search'])
            self.assertEqual(1152,report['context_comparison']['feature_dimensions'])
            self.assertFalse(report['context_comparison']['checkpoint_saved'])
            self.assertEqual(4,len(report['logistic_comparison']['fit_diagnostics']))
            self.assertEqual(8,report['glare_comparison']['scored_faces'])
            self.assertFalse(report['glare_comparison']['refused_folds'])
            for fit in report['logistic_comparison']['fit_diagnostics']:
                for side in fit['sides']:
                    self.assertNotIn(fit['excluded_group'],side['fit_groups'])
                    self.assertLessEqual(side['gradient_max'],1e-6)
            legacy=group_crossfit(manifest,root/'legacy',device='cpu',pretrained=False)
            self.assertNotIn('ridge_comparison',legacy)
            for name in ('global','side_aware'):
                self.assertEqual(legacy['predictions'][name],report['predictions'][name])
            for fold in report['folds']:
                self.assertNotIn(fold['group'],fold['fit_groups'])
                self.assertFalse(set(fold['train_indices'])&set(fold['held_indices']))
            for predictions in report['predictions'].values():
                self.assertTrue(all(r['group']==r['excluded_fit_group'] and r['split']=='train' for r in predictions))
            # A held group's truth may change metrics, but must not change its own fitted prediction.
            for a in rows[0]['side_annotations'].values():
                a['visibility_issues']=[] if a['visibility_issues'] else ['glare']
                a['labels']['gradable']=0 if a['visibility_issues'] else 1
            manifest.write_text('\n'.join(json.dumps(r) for r in rows))
            changed=group_crossfit(manifest,root/'changed',device='cpu',pretrained=False,compare_ridge=True,compare_context=True,compare_logistic=True,compare_glare_only=True)
            for name in ('global','side_aware','side_ridge','side_context','side_logistic'):
                first={r['side']:r['probabilities'][TARGET] for r in report['predictions'][name] if r['group']=='0'}
                after={r['side']:r['probabilities'][TARGET] for r in changed['predictions'][name] if r['group']=='0'}
                self.assertEqual(first,after)
            self.assertTrue(changed['refused_folds'])
            with self.assertRaisesRegex(ValueError,'Output exists'):
                group_crossfit(manifest,root/'first',pretrained=False)

    def test_insufficient_folds_do_not_save_misleading_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            manifest,_=test_visibility_model.VisibilityModelTest().setup_data(root)
            with self.assertRaisesRegex(ValueError,'No eligible'):
                group_crossfit(manifest,root/'out',pretrained=False)
            self.assertFalse((root/'out').exists())

    def test_duplicate_pixels_cannot_hide_behind_different_group_names(self):
        reject_duplicate_groups([dict(group='a',image_hashes=['same']),dict(group='a',image_hashes=['same'])])
        with self.assertRaisesRegex(ValueError,'different physical groups'):
            reject_duplicate_groups([dict(group='a',image_hashes=['same']),dict(group='b',image_hashes=['same'])])
