import copy
import json
from pathlib import Path
import tempfile
import unittest

from card_condition.evaluation_suite import assess_suite
from card_condition.release import file_sha256
from test_evaluation_suite import saved_suite


class SuiteSafetyTest(unittest.TestCase):
    def test_changed_report_bytes_rejected_even_when_counts_are_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            path = Path(reports['region_final']['path'])
            data = json.loads(path.read_text())
            data['predictions'][0]['probabilities']['edge_defect'] = .99
            data['metrics']['edge_defect']['tn'] -= 1
            data['metrics']['edge_defect']['fp'] += 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'report SHA256 mismatch'):
                assess_suite(*args, reports, root/'out.json')
            self.assertFalse((root/'out.json').exists())

    def test_wrong_identity_and_input_pins_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            path = Path(reports['region_final']['path'])
            original = json.loads(path.read_text())
            variants = [dict(original, model_sha256='0'*64), dict(original, threshold=.6)]
            for key in ('seal_sha256', 'candidate_sha256', 'operation'):
                data = copy.deepcopy(original)
                data['test_seal'][key] = 'wrong'
                variants.append(data)
            data = copy.deepcopy(original)
            data['input_hashes'].pop(str(args[3]))
            variants.append(data)
            for data in variants:
                path.write_text(json.dumps(data))
                supplied = copy.deepcopy(reports)
                supplied['region_final']['sha256'] = file_sha256(path)
                with self.assertRaises(ValueError):
                    assess_suite(*args, supplied, root/'out.json')
                self.assertFalse((root/'out.json').exists())

    def test_prediction_truth_geometry_duplicates_omissions_and_raw_metrics_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            path = Path(reports['region_final']['path'])
            original = json.loads(path.read_text())
            variants = []
            for key, value in (('group', 'other'), ('box', [0, 0, .5, .5]),
                               ('labels', {'edge_defect': 1, 'corner_defect': 1, 'surface_defect': 1})):
                data = copy.deepcopy(original)
                data['predictions'][0][key] = value
                variants.append(data)
            data = copy.deepcopy(original);data['predictions'].pop();variants.append(data)
            data = copy.deepcopy(original);data['predictions'].append(data['predictions'][0]);variants.append(data)
            data = copy.deepcopy(original);data['metrics']['edge_defect']['tn'] += 1;variants.append(data)
            for data in variants:
                path.write_text(json.dumps(data))
                supplied = copy.deepcopy(reports)
                supplied['region_final']['sha256'] = file_sha256(path)
                with self.assertRaises(ValueError):
                    assess_suite(*args, supplied, root/'out.json')
                self.assertFalse((root/'out.json').exists())

    def test_receipt_bytes_and_identity_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args, reports = saved_suite(root, 2)
            path = Path(reports['region_final']['path'])
            data = json.loads(path.read_text())
            receipt = Path(data['test_seal']['receipt'])
            used = json.loads(receipt.read_text())
            used['operation'] = 'side_final'
            receipt.write_text(json.dumps(used))
            with self.assertRaisesRegex(ValueError, 'receipt SHA256 mismatch'):
                assess_suite(*args, reports, root/'out.json')
            data['test_seal']['receipt_sha256'] = file_sha256(receipt)
            path.write_text(json.dumps(data))
            reports['region_final']['sha256'] = file_sha256(path)
            with self.assertRaisesRegex(ValueError, 'receipt identity mismatch'):
                assess_suite(*args, reports, root/'out.json')
