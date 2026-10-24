import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_pipeline import fixture
from card_condition.data import LABELS
from card_condition.routing_audit import routing_audit, threshold_analysis
from card_condition.side_experiment import side_rows


class RoutingAuditTest(unittest.TestCase):
    def test_threshold_ties_unknown_and_single_class(self):
        predictions = [{'labels': {k: truth for k in LABELS},
                        'probabilities': {k: value for k in LABELS}}
                       for truth, value in ((1,.3),(0,.3),(0,.8),(None,.99))]
        result=threshold_analysis(predictions)['surface_defect']
        self.assertEqual((1,2,1),(result['positive'],result['negative'],result['unknown']))
        point=next(p for p in result['points'] if p['threshold']==.3)
        self.assertEqual((1,2,0),(point['tp'],point['fp'],point['fn']))
        self.assertEqual(2,result['zero_miss_candidate']['fp'])
        self.assertEqual(1,result['zero_false_positive_candidate']['fn'])
        self.assertNotIn(.99,[p['threshold'] for p in result['points']])
        for prediction in predictions: prediction['labels']['gradable']=0
        single=threshold_analysis(predictions)['gradable']
        self.assertFalse(single['both_classes_present'])
        self.assertIsNone(single['zero_miss_candidate'])
        self.assertTrue(all(p['recall'] is None for p in single['points']))

    def test_counts_unsafe_and_never_saves_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, records = fixture(root)
            for row in records:
                row['side_annotations'] = {side: {'image': str(root / row[side]), 'box': [0, 0, 1, 1],
                                                   'labels': dict(row['labels'])} for side in ('front', 'back')}
            records[2]['side_annotations']['back']['labels']['surface_defect'] = None
            records[3]['side_annotations'] = {side: {'image': str(root / records[3][side]), 'box': [0, 0, 1, 1],
                                                       'labels': {'gradable': 1, **{k: 0 for k in LABELS[1:]}}}
                                                  for side in ('front', 'back')}
            manifest.write_text(''.join(json.dumps(row) + '\n' for row in records))
            rows, _, _ = side_rows(manifest, splits={'val'})
            predictions = [{'id': row['id'], 'labels': row['labels'],
                            'probabilities': {'gradable': .8, **{k: .1 for k in LABELS[1:]}}}
                           for row in rows]
            report = {'evaluation_kind': 'validation', 'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                      'supported': list(LABELS), 'predictions': predictions}
            report_path = root / 'report.json'
            report_path.write_text(json.dumps(report))
            output = root / 'routing.json'
            result = routing_audit(manifest, report_path, output)
            self.assertEqual(2, result['two_sided_cards'])
            self.assertEqual(2, result['trials'][0]['hypothetical_candidates'])
            self.assertEqual(1, result['trials'][0]['known_unsafe'])
            self.assertEqual(1, result['trials'][0]['visibly_clean'])
            self.assertEqual(0, result['trials'][-1]['hypothetical_candidates'])
            self.assertEqual(0, result['actual_calls_saved'])
            self.assertFalse(result['production_ready'])
            predictions[0]['labels']['gradable'] = 1
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'labels differ'):
                routing_audit(manifest, report_path, root / 'invalid.json')
