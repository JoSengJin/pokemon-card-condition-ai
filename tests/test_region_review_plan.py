import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_pipeline import fixture
from card_condition.region_review_plan import review_plan


class RegionReviewPlanTest(unittest.TestCase):
    def test_train_only_diversity_visibility_completion_and_no_label_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, rows = fixture(root)
            for row in rows:
                row['split'] = 'train'
                labels = {key: None for key in row['labels']}
                labels.update(gradable=1, corner_defect=0)
                row['side_annotations'] = {'front': {'image': str(root / row['front']),
                    'box': [0, 0, 1, 1], 'labels': labels, 'region_labels': {}}}
            rows[0]['side_annotations']['front']['visibility_issues'] = ['blur']
            rows[1]['side_annotations']['front']['visibility_issues'] = ['glare']
            rows[2]['side_annotations']['front'].update(visibility_issues=['glare'], glare_areas=['upper_right'])
            # Whole-card uncertainty must not block an explicitly observable face review.
            rows[2]['labels']['gradable'] = None
            rows[3]['side_annotations']['front']['region_labels'] = {
                'upper_left': {'corner_defect': 0, 'edge_defect': None, 'surface_defect': None}}
            rows += [{'id': 'val-unread', 'split': 'val', 'front': 'missing-val.png'},
                     {'id': 'test-unread', 'split': 'test', 'front': 'missing-test.png'}]
            manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            original = manifest.read_bytes()
            with patch('card_condition.region_review_plan.RegionAnalyzer') as model:
                analyzer = model.return_value
                analyzer.meta = {'supported': ['corner_defect']}
                analyzer.model_sha256 = 'model-hash'
                analyzer.analyze.side_effect = lambda image, box, area: {
                    'probabilities': {'corner_defect': .5 if area == 'upper_right' else .8}}
                result = review_plan(manifest, 'unused.pt', root / 'plan.json', 'cpu')
                self.assertEqual(3, len(result['selected']))
                self.assertEqual({'2', '4', '5'}, {task['id'] for task in result['selected']})
                self.assertEqual(3, len({task['group'] for task in result['selected']}))
                self.assertTrue(all(task['review_query'].startswith('?card=') for task in result['selected']))
                self.assertTrue(all(task['area'] == 'upper_right' for task in result['selected'] if task['id'] != '2'))
                self.assertNotEqual('upper_right', next(task['area'] for task in result['selected'] if task['id'] == '2'))
                self.assertEqual(1, result['normal_group_counts']['front']['corner_defect'])
                self.assertEqual(hashlib.sha256(original).hexdigest(), result['manifest_sha256'])
                self.assertFalse(result['labels_modified'])
                self.assertEqual(original, manifest.read_bytes())
                with self.assertRaisesRegex(ValueError, 'exists'):
                    review_plan(manifest, 'unused.pt', root / 'plan.json', 'cpu')
                # Group duplicates cannot consume a second place in the review batch.
                updated = copy.deepcopy(rows)
                updated[4]['group'] = updated[5]['group']
                manifest.write_text(''.join(json.dumps(row) + '\n' for row in updated))
                duplicate = review_plan(manifest, 'unused.pt', root / 'duplicate.json', 'cpu')
                self.assertEqual(2, len(duplicate['selected']))
                skipped = review_plan(manifest, 'unused.pt', root / 'skipped.json', 'cpu', skip_cards=['4'])
                self.assertEqual({'2'}, {task['id'] for task in skipped['selected']})
                self.assertEqual(['4'], skipped['skip_cards'])
                self.assertEqual([updated[4]['group']], skipped['skip_groups'])
                self.assertEqual(duplicate['normal_group_counts'], skipped['normal_group_counts'])
                updated[2]['side_annotations']['front']['region_reviews']={'lower_left':['corner_defect']}
                manifest.write_text(''.join(json.dumps(row) + '\n' for row in updated))
                completed = review_plan(manifest, 'unused.pt', root / 'completed.json', 'cpu')
                self.assertEqual(1, len(completed['selected']))
                self.assertTrue(all(task['id']!='2' for task in completed['selected']))
