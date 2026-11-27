"""Review 2026-11-27 I-6, I-7: AI-identical rows, unproven 'human', duplicate keys, and auto review editing the checker."""
import unittest
from pathlib import Path

from card_condition import experiment_record as recording
from card_condition.cross_review_auto_sources import model_file
from test_experiment_sidecars import SidecarBase


class SidecarRejectTest(SidecarBase):
    def test_ai_identical_and_unproven_human_rows_are_refused(self):
        for kind in ('ai_identical', 'human'):
            with self.subTest(kind=kind):
                self.facts[self.ids[0]]['rater_kind'] = kind
                self.declare()
                self.rejected()

    def test_duplicate_json_key_is_refused(self):
        self.declare()
        path = self.case.old / 'row_facts.json'
        path.write_text(path.read_text().replace('{', '{"_measure_sha256": "first",', 1))
        self.case.plan['sidecars']['row_facts']['sha256'] = recording.sha(path)
        self.rejected()

    def test_auto_review_cannot_edit_the_sidecar_checker(self):
        with self.assertRaises(ValueError):
            model_file(Path(__file__).resolve().parents[1], 'card_condition/experiment_sidecars.py')


if __name__ == '__main__':
    unittest.main()
