import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_pipeline import fixture
from card_condition.data import load_manifest
from card_condition.data_coverage import coverage_report
from card_condition.listing_model import photo_request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_a3_evaluation import prepare, request_for


def inputs(root):
    manifest, rows = fixture(root)
    for row in rows[:4]:
        row['side_annotations'] = dict(front=dict(image=str(root / row['front']), box=[0, 0, 1, 1],
            labels=dict(row['labels']), visibility_issues=[], box_reviewed=True))
    for row in rows[2:4]:
        row['labels']['gradable'] = row['side_annotations']['front']['labels']['gradable'] = 1
    normal, positive = rows[2]['side_annotations']['front'], rows[3]['side_annotations']['front']
    normal['region_labels'] = dict(upper_left=dict(corner_defect=None, edge_defect=None, surface_defect=0))
    positive.update(defect_points=[dict(label='surface_defect', x=.2, y=.2)],
                    visibility_issues=['glare'], glare_areas=['upper_center'])
    excluded = copy.deepcopy(rows[2]); excluded.update(id='excluded', excluded=True)
    # Malformed sealed test truth and missing images must never be opened or parsed.
    for row in rows[4:]:
        row.update(front='sealed-missing.png', labels='sealed', side_annotations='sealed')
    manifest.write_text('\n'.join(json.dumps(r) for r in [*rows, excluded]))
    coverage = root / 'coverage.json'
    coverage.write_text(json.dumps(coverage_report(manifest)))
    return manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(), coverage, hashlib.sha256(coverage.read_bytes()).hexdigest()


class PreparationTest(unittest.TestCase):
    def test_projection_preserves_truth_exclusions_paths_and_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); args = inputs(root)
            before = args[0].read_bytes(); out = root / 'prepared'
            with patch('torch.load', side_effect=AssertionError('No checkpoint loading')):
                result = prepare(*args, out)
            self.assertEqual((3, 2, 1), (result['rows'], result['active_rows'], result['excluded_rows']))
            self.assertEqual(before, args[0].read_bytes())
            original = load_manifest(args[0], splits={'val'}, require_gradable=False)
            exported = load_manifest(out / 'val.jsonl', require_gradable=False)
            self.assertEqual(original, exported)
            self.assertEqual({'val'}, {r['split'] for r in exported})
            self.assertTrue(exported[-1]['excluded'])
            counts = json.loads((out / 'denominators.json').read_text())
            source = json.loads(args[2].read_text())
            self.assertEqual([c for c in source['cells'] if c['split'] == 'val'], counts['c_cells'])
            self.assertEqual(1, len(counts['c_typed_points']))
            self.assertEqual(92, result['e2_required_cells'])
            self.assertIsNone(result['predictions']); self.assertIsNone(result['nondeferred_coverage'])
            self.assertFalse(result['independent'] or result['e2_verified'] or result['production_ready'])
            for entry in result['requests']:
                path = out / entry['path']; request = json.loads(path.read_text())
                self.assertEqual(entry['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual({'id', 'front', 'back'}, set(request))
                self.assertLessEqual(set(request['front']), {'image', 'box', 'visibility_issues', 'glare_areas'})
                self.assertEqual({'image'}, set(request['back']))
                row, unknown = photo_request(request)
                self.assertEqual(['back'], unknown)
                self.assertTrue(all(v is None for face in row['side_annotations'].values() for v in face['labels'].values()))

    def test_pins_and_changed_projection_are_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); args = list(inputs(root)); out = root / 'prepared'
            for field in (1, 3):
                wrong = list(args); wrong[field] = '0' * 64
                with self.subTest(field=field), self.assertRaises(ValueError): prepare(*wrong, out)
                self.assertFalse(out.exists())
            data = json.loads(args[2].read_text()); data['cells'][0]['unknown_units'] += 1
            args[2].write_text(json.dumps(data)); args[3] = hashlib.sha256(args[2].read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'Coverage differs'): prepare(*args, out)
            self.assertFalse(out.exists())

    def test_unknown_geometry_observation_and_partial_glare_remain_unknown(self):
        row = dict(id='one', front='/unused/front.png', back=None, side_annotations=dict(front=dict(
            box=[0, 0, 1, 1], box_reviewed=False, visibility_issues=['glare'], glare_areas=['center'])))
        request = request_for(row)
        self.assertNotIn('box', request['front']); self.assertNotIn('glare_areas', request['front'])
        self.assertEqual(['glare'], request['front']['visibility_issues'])
        row['side_annotations']['front']['box_reviewed'] = True
        self.assertEqual(['center'], request_for(row)['front']['glare_areas'])
        row['side_annotations']['front'].pop('visibility_issues')
        request = request_for(row)
        self.assertNotIn('visibility_issues', request['front']); self.assertNotIn('glare_areas', request['front'])
        self.assertEqual(['front'], photo_request(request)[1])

    def test_output_collision_and_end_of_run_drift_do_not_publish_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); args = inputs(root); out = root / 'prepared'
            out.mkdir(); (out / 'keep').write_text('original')
            with self.assertRaisesRegex(ValueError, 'Output exists'): prepare(*args, out)
            self.assertEqual('original', (out / 'keep').read_text())
            partial = root / 'partial'
            with patch('prepare_a3_evaluation.unchanged_inputs', side_effect=[None, None, ValueError('drift')]):
                with self.assertRaisesRegex(ValueError, 'drift'): prepare(*args, partial)
            self.assertFalse((partial / 'report.json').exists())

    def test_split_leakage_is_not_hidden_by_val_only_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); args = list(inputs(root))
            rows = [json.loads(line) for line in args[0].read_text().splitlines()]
            rows[2]['group'] = rows[0]['group']
            args[0].write_text('\n'.join(json.dumps(r) for r in rows))
            args[1] = hashlib.sha256(args[0].read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'across splits'): prepare(*args, root / 'bad')
            self.assertFalse((root / 'bad').exists())

    def test_val_coordinate_error_is_not_published_as_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); args = list(inputs(root))
            rows = [json.loads(line) for line in args[0].read_text().splitlines()]
            rows[3]['side_annotations']['front']['defect_points'] = [dict(label='corner_defect', x=.5, y=.5)]
            args[0].write_text('\n'.join(json.dumps(r) for r in rows))
            args[1] = hashlib.sha256(args[0].read_bytes()).hexdigest()
            args[2].write_text(json.dumps(coverage_report(args[0])))
            args[3] = hashlib.sha256(args[2].read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'coordinate audit'): prepare(*args, root / 'bad')
            self.assertFalse((root / 'bad').exists())
