import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import frozen_candidate, frozen_test
from card_condition.release import file_sha256
from test_frozen_test import inputs


def bundle(root):
    seal, sha, manifest, model = inputs(root)
    models = {op: root / (op + '.model') for op in frozen_candidate.OPERATIONS}
    for op, path in models.items():
        path.write_bytes(op.encode())
    source = root / 'source'
    source.mkdir()
    (source / 'code.py').write_text('source bytes')
    return seal, sha, manifest, models, source


class FrozenCandidateTest(unittest.TestCase):
    def test_planned_roles_once_and_new_candidate_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            seal, sha, manifest, models, source = bundle(root)
            candidate = root / 'candidate.json'
            with patch.object(frozen_candidate, 'SOURCE_ROOT', source), \
                 patch.object(frozen_candidate, 'version', return_value='fixture'), \
                 patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                frozen_candidate.pin_candidate(seal, sha, manifest, models, candidate, 'cpu')
                expected = file_sha256(candidate)
                options = dict(candidate_path=candidate, candidate_sha256=expected, device='cpu')
                for op, checkpoint in models.items():
                    receipt = frozen_test.claim_test(seal, sha, manifest, checkpoint, op, **options)
                    self.assertEqual(expected, receipt['candidate_sha256'])
                    self.assertEqual(op, receipt['operation'])
                    with self.assertRaisesRegex(ValueError, 'already used'):
                        frozen_test.claim_test(seal, sha, manifest, checkpoint, op, **options)
                self.assertEqual(3, len(list((root / 'ledger').glob('*.json'))))
                second = root / 'second.json'
                data = json.loads(candidate.read_text())
                data['extra_note'] = 'new plan cannot reopen the test'
                second.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'already used'):
                    frozen_test.claim_test(seal, sha, manifest, models['region_final'], 'region_final',
                                          candidate_path=second, candidate_sha256=file_sha256(second), device='cpu')

    def test_all_model_source_and_runtime_mutations_block_before_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            seal, sha, manifest, models, source = bundle(root)
            candidate = root / 'candidate.json'
            with patch.object(frozen_candidate, 'SOURCE_ROOT', source), \
                 patch.object(frozen_candidate, 'version', return_value='fixture'):
                frozen_candidate.pin_candidate(seal, sha, manifest, models, candidate, 'cpu')
                expected = file_sha256(candidate)
                for path in [*models.values(), source / 'code.py']:
                    original = path.read_bytes()
                    path.write_bytes(original + b'changed')
                    with self.assertRaises(ValueError):
                        frozen_candidate.read_candidate(candidate, expected, sha, models['region_final'], 'region_final', 'cpu')
                    path.write_bytes(original)
                extra = source / 'new.py'
                extra.touch()
                with self.assertRaisesRegex(ValueError, 'file set changed'):
                    frozen_candidate.read_candidate(candidate, expected, sha, models['region_final'], 'region_final', 'cpu')
                extra.unlink()
                with patch.object(frozen_candidate, 'version', return_value='different'):
                    with self.assertRaisesRegex(ValueError, 'runtime changed'):
                        frozen_candidate.read_candidate(candidate, expected, sha, models['region_final'], 'region_final', 'cpu')
                candidate.write_text(candidate.read_text() + ' ')
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    frozen_candidate.read_candidate(candidate, expected, sha, models['region_final'], 'region_final', 'cpu')

    def test_wrong_role_device_seal_path_and_missing_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            seal, sha, manifest, models, source = bundle(root)
            candidate = root / 'candidate.json'
            with patch.object(frozen_candidate, 'SOURCE_ROOT', source), \
                 patch.object(frozen_candidate, 'version', return_value='fixture'), \
                 patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                frozen_candidate.pin_candidate(seal, sha, manifest, {'region_final': models['region_final']}, candidate, 'cpu')
                expected = file_sha256(candidate)
                for role, device, seal_sha, checkpoint in (
                        ('side_final', 'cpu', sha, models['side_final']),
                        ('region_final', 'auto', sha, models['region_final']),
                        ('region_final', 'mps', sha, models['region_final']),
                        ('region_final', 'cpu', '0' * 64, models['region_final']),
                        ('region_final', 'cpu', sha, models['side_final'])):
                    with self.assertRaises(ValueError):
                        frozen_candidate.read_candidate(candidate, expected, seal_sha, checkpoint, role, device)
                for path, digest in ((candidate, None), (None, expected)):
                    with self.assertRaises(ValueError):
                        frozen_test.claim_test(seal, sha, manifest, models['region_final'], 'region_final',
                                              candidate_path=path, candidate_sha256=digest, device='cpu')
                with self.assertRaises(ValueError):
                    frozen_test.claim_test(None, None, manifest, models['region_final'], 'region_final',
                                          candidate_path=candidate, candidate_sha256=expected, device='cpu')
                self.assertFalse((root / 'ledger').exists())

    def test_candidate_cannot_reuse_a_previous_unplanned_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            seal, sha, manifest, models, source = bundle(root)
            candidate = root / 'candidate.json'
            with patch.object(frozen_candidate, 'SOURCE_ROOT', source), \
                 patch.object(frozen_candidate, 'version', return_value='fixture'), \
                 patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                frozen_test.claim_test(seal, sha, manifest, models['region_final'], 'region_final')
                frozen_candidate.pin_candidate(seal, sha, manifest, models, candidate, 'cpu')
                with self.assertRaisesRegex(ValueError, 'already used'):
                    frozen_test.claim_test(seal, sha, manifest, models['side_final'], 'side_final',
                                          candidate_path=candidate, candidate_sha256=file_sha256(candidate), device='cpu')

    def test_invalid_plan_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            seal, sha, manifest, models, source = bundle(root)
            candidate = root / 'candidate.json'
            with patch.object(frozen_candidate, 'SOURCE_ROOT', source), \
                 patch.object(frozen_candidate, 'version', return_value='fixture'):
                for selected, device in (({}, 'cpu'), ({'unknown': models['region_final']}, 'cpu'), (models, 'auto')):
                    with self.assertRaises(ValueError):
                        frozen_candidate.pin_candidate(seal, sha, manifest, selected, candidate, device)
                frozen_candidate.pin_candidate(seal, sha, manifest, models, candidate, 'cpu')
                original = candidate.read_bytes()
                with self.assertRaises(FileExistsError):
                    frozen_candidate.pin_candidate(seal, sha, manifest, models, candidate, 'cpu')
                self.assertEqual(original, candidate.read_bytes())
