import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import cli, frozen_test, frozen_test_cli, region_evaluation, side_evaluation, observation_heldout
from card_condition.release import file_sha256
from test_evaluation_inputs import evaluation_fixture


class FrozenTestEvaluationTest(unittest.TestCase):
    def test_manifest_seal_preserves_sources_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'region')
            before = manifest.read_bytes(), history.read_bytes()
            output = root / 'seal.json'
            report = frozen_test.seal_test(manifest, [history], output)
            self.assertEqual((manifest.read_bytes(), history.read_bytes()), before)
            self.assertEqual(2, len(report['physical_groups']))
            self.assertEqual(4, len(report['decoded_photo_sha256']))
            self.assertEqual(14, len(report['input_hashes']))
            self.assertFalse(report['d1_verified'])
            frozen_test.read_seal(output, file_sha256(output), manifest)
            with self.assertRaisesRegex(ValueError, 'Output exists'):
                frozen_test.seal_test(manifest, [history], output)
            for key in ('truth_sha256', 'grouping_sha256'):
                self.assertEqual(64, len(report[key]))

    def test_sealer_rejects_history_overlap_and_mixed_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'region')
            original = [json.loads(line) for line in manifest.read_text().splitlines()]
            for key, value in (('id', '0'), ('group', '0'), ('front', rows[0]['front']), ('split', 'train')):
                changed = copy.deepcopy(original)
                changed[0][key] = value
                manifest.write_text('\n'.join(json.dumps(r) for r in changed))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    frozen_test.seal_test(manifest, [history], root / 'seal.json')
                self.assertFalse((root / 'seal.json').exists())
            manifest.write_text('\n'.join(json.dumps(r) for r in original))
            for histories in ([], [history, history], [manifest]):
                with self.assertRaises(ValueError):
                    frozen_test.seal_test(manifest, histories, root / 'seal.json')

    def test_region_and_side_claim_before_inference_and_reject_second_attempt(self):
        for kind, module, constructor in (('region', region_evaluation, 'RegionAnalyzer'),
                                          ('side', side_evaluation, 'SideAnalyzer')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                seal = root / 'seal.json'
                frozen_test.seal_test(manifest, [history], seal)
                options = dict(test_seal=seal, test_seal_sha256=file_sha256(seal))
                args = (manifest, checkpoint, root / 'result.json', [history], 'cpu') if kind == 'region' else (
                    manifest, checkpoint, root / 'result.json', 'final', [history], 'cpu')
                evaluate = module.evaluate_regions if kind == 'region' else module.evaluate_sides
                with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                     patch.object(module, constructor, return_value=analyzer) as create:
                    report = evaluate(*args, **options)
                    self.assertEqual(file_sha256(seal), report['test_seal']['seal_sha256'])
                    self.assertEqual(4, report['rates_at_05']['corner_defect']['scored'])
                    create.reset_mock()
                    args = (*args[:2], root / 'retry.json', *args[3:])
                    with self.assertRaisesRegex(ValueError, 'already used'):
                        evaluate(*args, **options)
                    create.assert_not_called()
                    self.assertFalse((root / 'retry.json').exists())

    def test_failed_model_load_retains_claim_and_regression_rejects_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'side')
            seal = root / 'seal.json'
            frozen_test.seal_test(manifest, [history], seal)
            options = dict(test_seal=seal, test_seal_sha256=file_sha256(seal))
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(side_evaluation, 'SideAnalyzer', side_effect=RuntimeError('load failed')):
                with self.assertRaisesRegex(ValueError, 'only allowed for final'):
                    side_evaluation.evaluate_sides(manifest, checkpoint, root / 'out', 'regression', **options)
                self.assertFalse((root / 'ledger').exists())
                with self.assertRaisesRegex(RuntimeError, 'load failed'):
                    side_evaluation.evaluate_sides(manifest, checkpoint, root / 'out', 'final', [history], 'cpu', **options)
                self.assertFalse((root / 'out').exists())
                self.assertEqual(1, len(list((root / 'ledger').glob('*.json'))))
                with self.assertRaisesRegex(ValueError, 'already used'):
                    side_evaluation.evaluate_sides(manifest, checkpoint, root / 'out', 'final', [history], 'cpu', **options)

    def test_observation_loader_uses_seal_and_persists_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'side')
            records = [json.loads(line) for line in manifest.read_text().splitlines()]
            for i, record in enumerate(records):
                for annotation in record['side_annotations'].values():
                    annotation['labels']['gradable'] = 1
                    annotation['visibility_issues'] = ['glare'] if i else []
            manifest.write_text('\n'.join(json.dumps(r) for r in records))
            seal = root / 'seal.json'
            frozen_test.seal_test(manifest, [history], seal)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(observation_heldout, 'VisibilityAnalyzer') as model:
                model.return_value.analyze.return_value = dict(observation_limit_score=.9)
                report = observation_heldout.evaluate_heldout(checkpoint, manifest, root / 'out',
                    file_sha256(checkpoint), 'cpu', test_seal=seal, test_seal_sha256=file_sha256(seal))
            self.assertEqual('exposure_claimed', report['test_seal']['status'])
            self.assertEqual(report, json.loads((root / 'out/report.json').read_text()))

    def test_seal_cli_and_common_cli_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, 'region')
            seal = root / 'seal.json'
            output = io.StringIO()
            with redirect_stdout(output):
                status = frozen_test_cli.main([str(manifest), str(seal), '--history', str(history)])
            self.assertEqual(0, status)
            sha = json.loads(output.getvalue())['seal_sha256']
            argv = ['card-condition', 'region-evaluate', str(manifest), str(checkpoint), str(root / 'out.json'),
                    '--history', str(history), '--device', 'cpu', '--test-seal', str(seal), '--test-seal-sha256', sha]
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'), \
                 patch.object(region_evaluation, 'RegionAnalyzer', return_value=analyzer), \
                 patch('sys.argv', argv), redirect_stdout(io.StringIO()) as output:
                cli.main()
            self.assertEqual(sha, json.loads(output.getvalue())['test_seal']['seal_sha256'])
