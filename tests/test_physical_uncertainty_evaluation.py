from pathlib import Path
import json
import tempfile
import torch
import unittest
from unittest.mock import patch

from card_condition import region_evaluation, side_evaluation, observation_heldout
from card_condition.point_probe import digest
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

    def test_observation_evaluator_emits_same_event_definition_without_model_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint, manifest = root / 'checkpoint.pt', root / 'test.jsonl'
            torch.save(dict(development_groups=['development'], development_ids=['development'],
                            development_image_hashes=['0' * 64]), checkpoint)
            manifest.write_text('{}')
            rows = []
            for side in ('front', 'back'):
                for truth in (0, 1):
                    ident = f'{side}-{truth}'
                    image = root / (ident + '.fixture')
                    image.write_bytes(ident.encode())
                    rows.append(dict(id=ident, card_id=str(truth), group=str(truth), side=side,
                                     split='test', image=str(image), image_hashes=[digest(image)],
                                     box=[0, 0, 1, 1], labels={'observation_limited': truth},
                                     visibility_issues=['glare'] if truth else []))
            with patch.object(observation_heldout, 'visibility_rows', return_value=(rows, [])), \
                 patch.object(observation_heldout, 'VisibilityAnalyzer') as analyzer:
                analyzer.return_value.analyze.return_value = {'observation_limit_score': .9}
                report = observation_heldout.evaluate_heldout(checkpoint, manifest, root / 'out',
                                                             digest(checkpoint), 'cpu')
            self.assertEqual(4, analyzer.return_value.analyze.call_count)
            cells = [c for c in report['physical_card_uncertainty']['cells'] if c['supported']]
            self.assertEqual(2, len(cells))
            for cell in cells:
                self.assertEqual('observation_limited', cell['question'])
                self.assertEqual(1, cell['miss']['physical_cards'])
                self.assertEqual(0, cell['miss']['observed_events'])
                self.assertEqual(1, cell['false_alarm']['observed_events'])
            self.assertFalse(report['physical_card_uncertainty']['milestone_verified'])
            saved = json.loads((root / 'out/report.json').read_text())
            self.assertEqual(saved['physical_card_uncertainty'], report['physical_card_uncertainty'])
