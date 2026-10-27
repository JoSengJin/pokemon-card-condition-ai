import copy
import json
from pathlib import Path
import tempfile
import unittest

from card_condition.evaluation_typed_points import typed_point_cells


def fixture(n=5, per_card=4):
    records, predictions = [], []
    for i in range(n):
        row = dict(id=str(i), group=str(i), split='test', front='front', back='back',
                   _image_hashes=[f'front-{i}', f'back-{i}'], side_annotations={})
        for side in ('front', 'back'):
            points = [dict(label=q, x=(j+1)/(per_card+1), y=.1)
                      for q in ('corner_defect', 'edge_defect', 'surface_defect') for j in range(per_card)]
            row['side_annotations'][side] = dict(image=side, box=[0, 0, 1, 1],
                labels={q: 1 for q in ('gradable', 'centering_defect', 'corner_defect', 'edge_defect', 'surface_defect')},
                defect_points=points)
            predictions.extend(dict(card_id=str(i), side=side, label=p['label'], point=p, score=.5) for p in points)
        records.append(row)
    return records, dict(typed_point_predictions=predictions)


class TypedPointAssessmentTest(unittest.TestCase):
    def test_threshold_quantity_and_group_gates(self):
        records, report = fixture()
        supported = ['corner_defect', 'edge_defect', 'surface_defect']
        cells = typed_point_cells(report, records, supported)
        self.assertTrue(all(c['numeric_condition_met'] for c in cells.values()))
        report['typed_point_predictions'][0]['score'] = .49
        cell = typed_point_cells(report, records, supported)['corner_defect', 'front']
        self.assertEqual((20, 1, 5, .05), (cell['points'], cell['missed_points'], cell['physical_cards'], cell['false_negative_rate']))
        self.assertTrue(cell['numeric_condition_met'])
        report['typed_point_predictions'][1]['score'] = .49
        self.assertFalse(typed_point_cells(report, records, supported)['corner_defect', 'front']['numeric_condition_met'])
        for n, per_card in ((4, 5), (5, 3)):
            records, report = fixture(n, per_card)
            self.assertFalse(any(c['numeric_condition_met'] for c in typed_point_cells(report, records, supported).values()))

    def test_absent_empty_missing_score_and_unsupported_never_pass(self):
        records, report = fixture()
        cells = typed_point_cells({}, records, [])
        self.assertTrue(all(c['status'] == 'unmeasured' and c['points'] is None for c in cells.values()))
        report['typed_point_predictions'][0]['score'] = None
        cell = typed_point_cells(report, records, ['corner_defect', 'edge_defect', 'surface_defect'])['corner_defect', 'front']
        self.assertEqual((20, 1, None, False), (cell['points'], cell['unavailable_scores'], cell['false_negative_rate'], cell['numeric_condition_met']))
        for item in report['typed_point_predictions']:
            item['score'] = None
        self.assertFalse(any(c['numeric_condition_met'] for c in typed_point_cells(report, records, []).values()))
        self.assertFalse(any(c['numeric_condition_met'] for c in typed_point_cells({'typed_point_predictions': []}, [], []).values()))

    def test_identity_omission_duplicate_kind_geometry_and_alias_rejected(self):
        records, original = fixture()
        for mutation in ('omit', 'duplicate', 'kind', 'geometry', 'id', 'side', 'extra'):
            report = copy.deepcopy(original)
            items = report['typed_point_predictions']
            if mutation == 'omit':
                items.pop()
            elif mutation == 'duplicate':
                items.append(copy.deepcopy(items[0]))
            elif mutation == 'kind':
                items[0]['label'] = 'surface_defect'
            elif mutation == 'geometry':
                items[0]['point']['x'] = .99
            elif mutation == 'extra':
                items[0]['area'] = 'upper_left'
            else:
                items[0]['card_id' if mutation == 'id' else 'side'] = 'other'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                typed_point_cells(report, records, ['corner_defect', 'edge_defect', 'surface_defect'])
        records[1]['_image_hashes'] = records[0]['_image_hashes']
        with self.assertRaisesRegex(ValueError, 'aliased'):
            typed_point_cells(original, records, [])

    def test_bad_scores_and_nonpositive_source_rejected(self):
        records, original = fixture()
        for score in (True, float('nan'), float('inf'), -.01, 1.01, '.5'):
            report = copy.deepcopy(original)
            report['typed_point_predictions'][0]['score'] = score
            with self.subTest(score=score), self.assertRaises(ValueError):
                typed_point_cells(report, records, ['corner_defect', 'edge_defect', 'surface_defect'])
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            typed_point_cells(original, records, [])
        records[0]['side_annotations']['front']['labels']['corner_defect'] = None
        with self.assertRaisesRegex(ValueError, 'sealed source'):
            typed_point_cells(original, records, ['corner_defect', 'edge_defect', 'surface_defect'])

    def test_saved_suite_consumes_bound_points_and_rejects_modified_report(self):
        from test_evaluation_suite import saved_suite
        from card_condition.data import load_manifest
        from card_condition.evaluation_suite import assess_suite
        from card_condition.release import file_sha256
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, n=5, typed_points=True)
            path = Path(reports['region_final']['path'])
            report = json.loads(path.read_text())
            report['typed_point_predictions'] = [dict(card_id=r['id'], side=side, label=p['label'], point=p, score=.5)
                for r in load_manifest(args[0], require_gradable=False)
                for side, annotation in r['side_annotations'].items() for p in annotation.get('defect_points', [])]
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                assess_suite(*args, reports, root/'bad.json')
            self.assertFalse((root/'bad.json').exists())
            reports['region_final']['sha256'] = file_sha256(path)
            before = path.read_bytes()
            result = assess_suite(*args, reports, root/'ok.json')
            self.assertTrue(result['numeric_gates']['c_typed_point_all'])
            self.assertFalse(result['numeric_gates']['c_raw_all_questions'])
            self.assertFalse(result['d2_verified'] or result['production_ready'])
            self.assertEqual(before, path.read_bytes())
            report['typed_point_predictions'].pop()
            path.write_text(json.dumps(report))
            reports['region_final']['sha256'] = file_sha256(path)
            with self.assertRaisesRegex(ValueError, 'omitted'):
                assess_suite(*args, reports, root/'omitted.json')
            self.assertFalse((root/'omitted.json').exists())
