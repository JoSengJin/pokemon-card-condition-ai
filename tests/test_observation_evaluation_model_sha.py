from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from card_condition import observation_heldout, frozen_test
from card_condition.cli import main
from card_condition.release import file_sha256
from card_condition.evaluation_inputs import matched_model
from test_evaluation_inputs import evaluation_fixture


def observation_case(root):
    manifest, history, checkpoint, records, analyzer = evaluation_fixture(root, 'side')
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    for i, row in enumerate(rows):
        for a in row['side_annotations'].values():
            a['labels']['gradable'] = 1
            a['visibility_issues'] = ['glare'] if i else []
    manifest.write_text('\n'.join(json.dumps(r) for r in rows))
    return checkpoint, manifest, history


class ObservationEvaluationShaTest(unittest.TestCase):
    def test_mismatched_loaded_model_is_rejected_before_photo_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkpoint, manifest, history = observation_case(root)
            model = Mock(model_sha256='f'*64)
            model.analyze.return_value = dict(observation_limit_score=.9)
            with patch.object(observation_heldout, 'VisibilityAnalyzer', return_value=model):
                with self.assertRaisesRegex(ValueError, 'different checkpoint'):
                    observation_heldout.evaluate_heldout(checkpoint, manifest, root/'out', file_sha256(checkpoint), 'cpu')
            model.analyze.assert_not_called()
            self.assertFalse((root/'out').exists())

    def test_matching_loaded_model_keeps_frozen_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkpoint, manifest, history = observation_case(root)
            expected = file_sha256(checkpoint)
            model = Mock(model_sha256=expected)
            model.analyze.return_value = dict(observation_limit_score=.9)
            with patch.object(observation_heldout, 'VisibilityAnalyzer', return_value=model):
                report = observation_heldout.evaluate_heldout(checkpoint, manifest, root/'out', expected, 'cpu')
            self.assertEqual(expected, report['model_sha256'])
            self.assertEqual(4, model.analyze.call_count)
            self.assertEqual(report, json.loads((root/'out/report.json').read_text()))

    def test_sealed_failure_keeps_claim_and_blocks_automatic_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkpoint, manifest, history = observation_case(root)
            seal = root/'seal.json'
            frozen_test.seal_test(manifest, [history], seal)
            model = Mock(model_sha256='f'*64)
            options = dict(test_seal=seal, test_seal_sha256=file_sha256(seal))
            with patch.object(frozen_test, 'LEDGER', root/'ledger'), \
                 patch.object(observation_heldout, 'VisibilityAnalyzer', return_value=model) as create:
                with self.assertRaisesRegex(ValueError, 'different checkpoint'):
                    observation_heldout.evaluate_heldout(checkpoint, manifest, root/'out', file_sha256(checkpoint), 'cpu', **options)
                with self.assertRaisesRegex(ValueError, 'already used'):
                    observation_heldout.evaluate_heldout(checkpoint, manifest, root/'out', file_sha256(checkpoint), 'cpu', **options)
                create.assert_called_once()
            model.analyze.assert_not_called()
            self.assertEqual(1, len(list((root/'ledger').glob('*.json'))))
            self.assertFalse((root/'out').exists())

    def test_cli_returns_error_json_without_a_success_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkpoint, manifest, history = observation_case(root)
            model = Mock(model_sha256='f'*64)
            argv = ['card-condition', 'visibility-heldout', str(checkpoint), str(manifest), str(root/'out'),
                    '--expected-model-sha256', file_sha256(checkpoint), '--device', 'cpu']
            with patch.object(observation_heldout, 'VisibilityAnalyzer', return_value=model), \
                 patch('sys.argv', argv), redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as done:
                    main()
            self.assertEqual(1, done.exception.code)
            self.assertEqual('', out.getvalue())
            self.assertIn('different checkpoint', json.loads(err.getvalue())['error'])
            self.assertTrue(json.loads(err.getvalue())['requires_gemini'])
            model.analyze.assert_not_called()

    def test_changed_checkpoint_alias_is_a_structured_validation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old, new, alias = root/'old.pt', root/'new.pt', root/'current.pt'
            old.write_bytes(b'first fixture')
            new.write_bytes(b'second fixture')
            alias.symlink_to(old)
            hashes = {str(alias.resolve()): file_sha256(old)}
            alias.unlink()
            alias.symlink_to(new)
            with self.assertRaisesRegex(ValueError, 'different checkpoint'):
                matched_model(Mock(model_sha256=file_sha256(new)), hashes, alias)
            with self.assertRaisesRegex(ValueError, 'different checkpoint'):
                matched_model(Mock(model_sha256=None), {}, alias)
