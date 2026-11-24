import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_experiment_record as fixture
from card_condition import experiment_record as recording
from card_condition.acceptance_caps import cap_status
from card_condition.cross_review_auto import render_result
from card_condition.cross_review_auto_sources import model_file
from card_condition.cross_review_evidence import latest_packet

CAPS = dict(max_fp=0, max_fn=0)


class AcceptanceCapsTest(unittest.TestCase):
    def setUp(self):
        self.case = fixture.ExperimentRecordTest('test_all_required_and_primary_pass')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.required_cohort()

    def one_class_cohort(self, target, scores):
        """Required cohort with only defect (1) or only normal (0) rows; returns its result after a full run."""
        path = self.case.root / 'artifacts/held/reference.json'
        rows = [dict(r, target=target) for r in recording.read(path)['rows']]
        before = [.9, .9] if target else [.1, .1]
        recording.save(path, dict(rows=rows, before_scores=before, scores=before))
        code, folder, record = self.case.run_case(self.case.required_body(scores))
        self.assertEqual((code, record['status']), (0, 'completed'))
        return recording.read(folder / 'result.json'), folder

    def test_cap_status_by_denominator(self):
        for counts, expected in [
                (dict(tp=2, tn=0, fp=0, fn=0), dict(max_fp='unmeasured', max_fn='passed')),
                (dict(tp=1, tn=0, fp=0, fn=1), dict(max_fp='unmeasured', max_fn='failed')),
                (dict(tp=0, tn=2, fp=0, fn=0), dict(max_fp='passed', max_fn='unmeasured')),
                (dict(tp=1, tn=0, fp=1, fn=0), dict(max_fp='failed', max_fn='passed'))]:
            with self.subTest(counts=counts):
                self.assertEqual(cap_status(CAPS, counts), expected)

    def test_one_class_required_cohort_keeps_verdict_and_records_unmeasured_cap(self):
        result, folder = self.one_class_cohort(1, '[.9,.9]')
        cohort = result['required_cohorts'][0]
        self.assertEqual((result['acceptance_passed'], cohort['acceptance_passed']), (True, True))  # same verdict as before zero-denominator-unmeasured
        self.assertEqual(cohort['acceptance_caps'], dict(max_fp='unmeasured', max_fn='passed'))
        self.assertEqual(result['acceptance_caps'], dict(max_fp='passed', max_fn='passed'))
        render_result(self.case.root, folder)
        result, _ = self.one_class_cohort(0, '[.1,.9]')
        self.assertFalse(result['acceptance_passed'])
        self.assertEqual(result['required_cohorts'][0]['acceptance_caps'], dict(max_fp='failed', max_fn='unmeasured'))
        self.assertIn('held', str(latest_packet(self.case.root)['evidence']['latest_result']['summary']['required_cohorts']))

    def test_unmeasured_cap_does_not_block_the_next_reference(self):
        _, folder = self.one_class_cohort(1, '[.9,.9]')
        self.case.plan['reference_result'] = str((folder / 'result.json').relative_to(self.case.root))
        _, folder, record = self.case.run_case(self.case.required_body('[.9,.9]'))
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(recording.read(folder / 'reference.json')['required_cohorts'][0].get('acceptance_caps'), None)

    def test_declared_counts_must_match_frozen_truth_before_the_child_starts(self):
        counts = dict(primary=dict(defect=1, normal=2), held=dict(defect=1, normal=1))
        self.case.plan['evaluation_counts'] = counts
        _, folder, record = self.case.run_case(self.case.required_body())
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(recording.read(folder / 'plan.json')['evaluation_counts'], counts)
        for wrong in (dict(primary=counts['primary']), dict(counts, held=dict(defect=2, normal=0)), dict(counts, other=counts['held']), {}, None):
            with self.subTest(wrong=wrong), patch('subprocess.Popen') as child:
                self.case.plan['evaluation_counts'] = wrong
                with self.assertRaisesRegex(ValueError, 'do not match'):
                    recording.prepare(self.case.root, self.case.plan, ['anything'])
                child.assert_not_called()

        del self.case.plan['evaluation_counts']  # 'primary' stays a valid cohort ID for plans without the field
        self.case.plan['required_cohorts'][0]['id'] = 'primary'
        _, _, record = self.case.run_case(self.case.required_body())
        self.assertEqual(record['status'], 'completed')
        self.case.plan['evaluation_counts'] = {}
        with self.assertRaisesRegex(ValueError, 'primary'):
            recording.prepare(self.case.root, self.case.plan, ['anything'])

    def test_automatic_edits_cannot_touch_the_cap_judgment(self):
        (self.case.root / 'card_condition/acceptance_caps.py').write_text('')
        with self.assertRaises(ValueError):
            model_file(self.case.root, 'card_condition/acceptance_caps.py')


if __name__ == '__main__':
    unittest.main()
