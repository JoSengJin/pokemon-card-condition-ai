from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from card_condition import frozen_test
from card_condition.release import file_sha256


def inputs(root, ident='test'):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest, history, photo, model = [root / name for name in ('test.jsonl', 'history.jsonl', 'photo', 'model')]
    for path in (manifest, history, photo, model):
        path.write_bytes((ident + path.name).encode())
    seal = root / 'seal.json'
    seal.write_text(json.dumps(dict(schema_version=1, kind='frozen_test_inputs', manifest=str(manifest),
        manifest_sha256=file_sha256(manifest), history=[str(history)], physical_groups=[ident],
        decoded_photo_sha256=[file_sha256(photo)],
        input_hashes={str(p): file_sha256(p) for p in (manifest, history, photo)})))
    return seal, file_sha256(seal), manifest, model


class FrozenTestUseTest(unittest.TestCase):
    def test_copies_new_candidates_and_reseals_cannot_reuse_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seal, sha, manifest, model = inputs(root)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                claim = frozen_test.claim_test(seal, sha, manifest, model, 'region_final')
                self.assertEqual('exposure_claimed', claim['status'])
                receipt = json.loads(Path(claim['receipt']).read_text())
                self.assertEqual(file_sha256(model), receipt['model_sha256'])
                self.assertEqual(file_sha256(claim['receipt']), claim['receipt_sha256'])
                copy = root / 'copy.json'
                shutil.copyfile(seal, copy)
                model.write_bytes(b'new candidate')
                for path in (seal, copy):
                    with self.assertRaisesRegex(ValueError, 'already used'):
                        frozen_test.claim_test(path, sha, manifest, model, 'observation_final')
                changed = json.loads(seal.read_text())
                changed['sealed_at'] = 'new time does not erase exposure'
                seal.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'already used'):
                    frozen_test.claim_test(seal, file_sha256(seal), manifest, model, 'side_final')
                self.assertEqual(1, len(list((root / 'ledger').glob('*.json'))))

    def test_every_frozen_file_and_seal_is_checked_before_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seal, sha, manifest, model = inputs(root)
            frozen = json.loads(seal.read_text())['input_hashes']
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                for name in frozen:
                    path = Path(name)
                    original = path.read_bytes()
                    path.write_bytes(original + b'changed')
                    with self.assertRaisesRegex(ValueError, 'input changed'):
                        frozen_test.claim_test(seal, sha, manifest, model, 'final')
                    path.write_bytes(original)
                original = seal.read_bytes()
                seal.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'seal SHA256 mismatch'):
                    frozen_test.claim_test(seal, sha, manifest, model, 'final')
                self.assertFalse((root / 'ledger').exists())

    def test_missing_controls_invalid_identity_and_legacy_noop(self):
        self.assertIsNone(frozen_test.claim_test(None, None, None, None, 'legacy'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seal, sha, manifest, model = inputs(root)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                for path, expected in ((None, sha), (seal, None), (seal, 'x' * 64)):
                    with self.assertRaises(ValueError):
                        frozen_test.claim_test(path, expected, manifest, model, 'final')
                with self.assertRaisesRegex(ValueError, 'identity'):
                    frozen_test.claim_test(seal, sha, root / 'different.jsonl', model, 'final')
                data = json.loads(seal.read_text())
                for key, value in (('physical_groups', []), ('decoded_photo_sha256', ['invalid']),
                                   ('history', []), ('input_hashes', {})):
                    bad = root / 'bad.json'
                    bad.write_text(json.dumps(dict(data, **{key: value})))
                    with self.assertRaises(ValueError):
                        frozen_test.claim_test(bad, file_sha256(bad), manifest, model, 'final')
                self.assertFalse((root / 'ledger').exists())

    def test_two_concurrent_calls_create_only_one_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = inputs(root)
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                def attempt(number):
                    try:
                        frozen_test.claim_test(*args, 'final')
                        return 'claimed'
                    except ValueError:
                        return 'blocked'
                with ThreadPoolExecutor(max_workers=2) as pool:
                    self.assertCountEqual(['claimed', 'blocked'], list(pool.map(attempt, range(2))))
                self.assertEqual(1, len(list((root / 'ledger').glob('*.json'))))

    def test_overlap_by_either_group_or_pixels_and_corrupt_receipts_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = inputs(root / 'a', 'a')
            second = inputs(root / 'b', 'b')
            with patch.object(frozen_test, 'LEDGER', root / 'ledger'):
                frozen_test.claim_test(*first, 'final')
                seal, sha, manifest, model = second
                data = json.loads(seal.read_text())
                original = seal.read_bytes()
                for key in ('physical_groups', 'decoded_photo_sha256'):
                    changed = dict(data, **{key: json.loads(first[0].read_text())[key]})
                    seal.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, 'already used'):
                        frozen_test.claim_test(seal, file_sha256(seal), manifest, model, 'final')
                seal.write_bytes(original)
                frozen_test.claim_test(*second, 'final')
                self.assertEqual(2, len(list((root / 'ledger').glob('*.json'))))
                (root / 'ledger' / 'corrupt.json').write_text('{}')
                third = inputs(root / 'c', 'c')
                with self.assertRaisesRegex(ValueError, 'manual audit'):
                    frozen_test.claim_test(*third, 'final')
