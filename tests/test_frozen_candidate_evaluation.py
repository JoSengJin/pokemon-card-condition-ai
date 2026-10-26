from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import torch
import unittest
from unittest.mock import patch

from card_condition import cli, frozen_candidate, frozen_candidate_cli, frozen_test
from card_condition import region_evaluation, side_evaluation, observation_heldout
from card_condition.release import file_sha256
from test_evaluation_inputs import evaluation_fixture


def prepared(root):
    manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'region')
    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    for i, record in enumerate(records):
        for annotation in record['side_annotations'].values():
            annotation['labels']['gradable'] = 1
            annotation['visibility_issues'] = ['glare'] if i else []
    manifest.write_text('\n'.join(json.dumps(r) for r in records))
    models = {'region_final': checkpoint}
    for op in ('side_final', 'observation_final'):
        models[op] = root / (op + '.pt')
        shutil.copyfile(checkpoint, models[op])
    seal, candidate = root / 'seal.json', root / 'candidate.json'
    frozen_test.seal_test(manifest, [history], seal)
    frozen_candidate.pin_candidate(seal, file_sha256(seal), manifest, models, candidate, 'cpu')
    options = dict(test_seal=seal, test_seal_sha256=file_sha256(seal),
                   test_candidate=candidate, test_candidate_sha256=file_sha256(candidate))
    return manifest, history, models, analyzer, candidate, options


class CandidateEvaluationTest(unittest.TestCase):
    def test_three_evaluators_share_only_the_same_frozen_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, models, analyzer, candidate, options = prepared(root)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(region_evaluation, 'RegionAnalyzer', return_value=analyzer), \
                 patch.object(side_evaluation, 'SideAnalyzer', return_value=analyzer), \
                 patch.object(observation_heldout, 'VisibilityAnalyzer') as observation:
                observation.return_value.model_sha256 = file_sha256(models['observation_final'])
                observation.return_value.analyze.return_value = dict(observation_limit_score=.9)
                reports = [region_evaluation.evaluate_regions(manifest, models['region_final'], root / 'region.json',
                                                              [history], 'cpu', **options),
                           side_evaluation.evaluate_sides(manifest, models['side_final'], root / 'side.json',
                                                         'final', [history], 'cpu', **options),
                           observation_heldout.evaluate_heldout(models['observation_final'], manifest, root / 'observation',
                                                              file_sha256(models['observation_final']), 'cpu', **options)]
                self.assertEqual(3, len(list((root / 'ledger').glob('*.json'))))
                self.assertEqual(set(models), {r['test_seal']['operation'] for r in reports})
                self.assertTrue(all(r['test_seal']['candidate_sha256'] == file_sha256(candidate) for r in reports))
                with self.assertRaisesRegex(ValueError, 'already used'):
                    region_evaluation.evaluate_regions(manifest, models['region_final'], root / 'retry', [history], 'cpu', **options)
                for report in reports:
                    self.assertTrue(all(str(path) in report['input_hashes'] for path in models.values()))
                    self.assertFalse(report['physical_card_uncertainty']['milestone_verified'])

    def test_candidate_cli_and_evaluator_cli_share_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, models, analyzer, candidate, options = prepared(root)
            cli_candidate = root / 'cli-candidate.json'
            with redirect_stdout(io.StringIO()) as output:
                status = frozen_candidate_cli.main([str(manifest), str(options['test_seal']), str(cli_candidate),
                    '--seal-sha256', options['test_seal_sha256'], '--device', 'cpu', '--region', str(models['region_final'])])
            self.assertEqual(0, status)
            expected = json.loads(output.getvalue())['candidate_sha256']
            argv = ['card-condition', 'region-evaluate', str(manifest), str(models['region_final']), str(root / 'out.json'),
                    '--history', str(history), '--device', 'cpu', '--test-seal', str(options['test_seal']),
                    '--test-seal-sha256', options['test_seal_sha256'], '--test-candidate', str(cli_candidate),
                    '--test-candidate-sha256', expected]
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(region_evaluation, 'RegionAnalyzer', return_value=analyzer), \
                 patch('sys.argv', argv), redirect_stdout(io.StringIO()) as output:
                cli.main()
            self.assertEqual(expected, json.loads(output.getvalue())['test_seal']['candidate_sha256'])

    def test_sibling_checkpoint_change_during_inference_rejects_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, models, analyzer, candidate, options = prepared(root)
            result = analyzer.analyze.return_value
            def changed(*args, **kwargs):
                models['side_final'].write_bytes(b'changed during region inference')
                return result
            analyzer.analyze.side_effect = changed
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(region_evaluation, 'RegionAnalyzer', return_value=analyzer):
                with self.assertRaisesRegex(ValueError, 'inputs changed'):
                    region_evaluation.evaluate_regions(manifest, models['region_final'], root / 'out.json',
                                                       [history], 'cpu', **options)
            self.assertFalse((root / 'out.json').exists())
            self.assertEqual(1, len(list((root / 'ledger').glob('*.json'))))

    def test_mutated_candidate_models_fail_before_second_claim_or_model_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, models, analyzer, candidate, options = prepared(root)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(region_evaluation, 'RegionAnalyzer', return_value=analyzer):
                region_evaluation.evaluate_regions(manifest, models['region_final'], root / 'first.json', [history], 'cpu', **options)
                meta = torch.load(models['side_final'], weights_only=True)
                torch.save(dict(meta, candidate_test_change=True), models['side_final'])
                with patch.object(side_evaluation, 'SideAnalyzer') as create:
                    with self.assertRaisesRegex(ValueError, 'Candidate checkpoint changed'):
                        side_evaluation.evaluate_sides(manifest, models['side_final'], root / 'second.json',
                                                       'final', [history], 'cpu', **options)
                    create.assert_not_called()
                self.assertEqual(1, len(list((root / 'ledger').glob('*.json'))))
