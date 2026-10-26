from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import region_evaluation, side_evaluation
from test_evaluation_inputs import evaluation_fixture, evaluate


class UncertaintyEvaluationTest(unittest.TestCase):
    def test_both_evaluators_emit_card_uncertainty_without_changing_raw_counts(self):
        for kind, module, constructor in (('region', region_evaluation, 'RegionAnalyzer'),
                                          ('side', side_evaluation, 'SideAnalyzer')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                with patch.object(module, constructor, return_value=analyzer):
                    report = evaluate(kind, module, manifest, history, checkpoint, root / 'out.json')
                self.assertEqual(4, report['rates_at_05']['corner_defect']['scored'])
                self.assertEqual(.5, report['rates_at_05']['corner_defect']['accuracy'])
                uncertainty = report['physical_card_uncertainty']
                self.assertFalse(uncertainty['milestone_verified'])
                self.assertFalse(uncertainty['all_numeric_conditions_met'])
                self.assertEqual(10, len(uncertainty['cells']))
                corners = [c for c in uncertainty['cells'] if c['question'] == 'corner_defect']
                self.assertTrue(all(c['miss']['physical_cards'] == 1 for c in corners))
                self.assertTrue(all(c['miss']['observed_events'] == 0 for c in corners))
                self.assertTrue(all(c['false_alarm']['physical_cards'] == 1 for c in corners))
                self.assertTrue(all(c['false_alarm']['observed_events'] == 1 for c in corners))
