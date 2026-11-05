from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.pilot_summary import summarize


def cohort_entry(index=0):
    return dict(schema_version=1, kind='listing_predict_usage', outcome='ok', error_type=None,
        started_unix=index*60., total_seconds=10., analyze_seconds=4., request_id=f'card-{index}', faces=2, warm=True,
        release=dict(release_id='same-label', package_version='fixture', input_contract='listing-request-v1',
                     manifest_sha256='a'*64, checkpoint_sha256={'region':'b'*64}),
        release_requested=True, attempted_release_id='same-label', model_sha256='b'*64,
        report_sha256=f'report-{index}', cells=dict(normal=1, defect=0, unknown=0),
        device='cpu', image_size=224, batched_views=False)


class FixedPilotCohortTest(unittest.TestCase):
    def test_fixed_declared_identity_and_configuration_allow_numeric_latency_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            path.write_text(''.join(json.dumps(cohort_entry(i))+'\n' for i in range(2)))
            report = summarize(path)
            group = report['releases'][0]
            self.assertTrue(group['pinned'])
            self.assertEqual('consistent', group['release_identity_status'])
            self.assertEqual((4., True), (group['conditions']['warm_pair_p95_seconds']['value'], group['conditions']['warm_pair_p95_seconds']['met']))
            config = group['conditions']['fixed_declared_execution_configuration']
            self.assertEqual('fixed', config['status'])
            self.assertEqual(1, len(config['cohorts']))
            self.assertFalse(config['hardware_identity_verified'])
            self.assertFalse(report['pilot_certified'])

    def test_mixed_or_missing_device_size_batch_never_uses_a_pooled_p95(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            for field, value in (('device', 'mps'), ('image_size', 448), ('batched_views', True)):
                rows = [cohort_entry(0), cohort_entry(1)]
                rows[1][field] = value
                path.write_text(''.join(json.dumps(e)+'\n' for e in rows))
                group = summarize(path)['releases'][0]
                self.assertEqual('mixed', group['conditions']['fixed_declared_execution_configuration']['status'])
                self.assertEqual((None, False), (group['conditions']['warm_pair_p95_seconds']['value'], group['conditions']['warm_pair_p95_seconds']['met']))
                self.assertEqual(2, len(group['conditions']['fixed_declared_execution_configuration']['cohorts']))
                rows[1].pop(field)
                path.write_text(''.join(json.dumps(e)+'\n' for e in rows))
                group = summarize(path)['releases'][0]
                self.assertIsNone(group['conditions']['warm_pair_p95_seconds']['met'])
                self.assertEqual(1, group['conditions']['fixed_declared_execution_configuration']['unknown_successful_records'])

    def test_same_release_label_with_different_frozen_identity_is_not_a_single_pinned_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            rows = [cohort_entry(0), cohort_entry(1)]
            rows[1]['release'].update(manifest_sha256='c'*64, checkpoint_sha256={'region':'d'*64})
            rows[1]['model_sha256'] = 'd'*64
            path.write_text(''.join(json.dumps(e)+'\n' for e in rows))
            group = summarize(path)['releases'][0]
            self.assertEqual(2, group['requests'])
            self.assertFalse(group['pinned'])
            self.assertEqual('conflict', group['release_identity_status'])
            self.assertEqual(2, len(group['release_identity_variants']))
            self.assertFalse(group['conditions']['warm_pair_p95_seconds']['met'])
            self.assertIsNone(group['conditions']['warm_pair_p95_seconds']['value'])
            self.assertFalse(group['conditions']['fixed_release_identity']['met'])

    def test_label_only_legacy_and_unidentified_failed_attempts_remain_unmeasured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            legacy = cohort_entry(0)
            legacy['release'] = dict(release_id='same-label')
            for key in ('device', 'image_size', 'batched_views'):
                legacy.pop(key)
            path.write_text(json.dumps(legacy)+'\n')
            group = summarize(path)['releases'][0]
            self.assertFalse(group['pinned'])
            self.assertIsNone(group['conditions']['warm_pair_p95_seconds']['met'])
            failed = cohort_entry(1)
            failed.update(outcome='error', release=None, analyze_seconds=None, cells=None, report_sha256=None)
            path.write_text(''.join(json.dumps(e)+'\n' for e in [cohort_entry(0), failed]))
            group = summarize(path)['releases'][0]
            self.assertEqual((2, 1), (group['requests'], group['errors']))
            self.assertEqual(.5, group['conditions']['recorded_error_rate']['value'])
            self.assertIsNone(group['conditions']['recorded_error_rate']['met'])
            self.assertEqual(1, group['conditions']['fixed_release_identity']['unidentified_records'])

    def test_impossible_numbers_counts_and_model_pin_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            for key, value in (('started_unix', -1), ('started_unix', float('nan')), ('total_seconds', float('inf')),
                               ('total_seconds', True), ('analyze_seconds', -1), ('analyze_seconds', 11),
                               ('faces', True), ('warm', 1), ('outcome', 'ignored'), ('release_requested', False),
                               ('cells', dict(normal=-1, defect=0, unknown=0)),
                               ('cells', dict(normal=True, defect=0, unknown=0)), ('model_sha256', 'c'*64)):
                row = cohort_entry(0);row[key] = value
                path.write_text(json.dumps(row)+'\n')
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    summarize(path)
            missing = cohort_entry(0);missing.pop('release')
            path.write_text(json.dumps(missing)+'\n')
            with self.assertRaises(ValueError):
                summarize(path)

    def test_cli_discloses_a_mixed_configuration_without_certifying_pilot(self):
        from card_condition.cli import main
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            rows = [cohort_entry(0), cohort_entry(1)]
            rows[1]['device'] = 'mps'
            path.write_text(''.join(json.dumps(e)+'\n' for e in rows))
            with patch('sys.argv', ['card-condition', 'pilot-summary', str(path)]), redirect_stdout(io.StringIO()) as output:
                main()
            report = json.loads(output.getvalue())
            self.assertFalse(report['pilot_certified'])
            self.assertFalse(report['releases'][0]['conditions']['warm_pair_p95_seconds']['met'])
