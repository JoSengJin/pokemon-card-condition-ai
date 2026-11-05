from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.release import read_release, file_sha256


def release_fixture(root):
    model = root / 'fixture.model'
    model.write_bytes(b'synthetic checkpoint bytes, not a trained model')
    entry = dict(file=model.name, sha256=file_sha256(model))
    manifest = dict(release_id='fixture', package_version='fixture-version', input_contract='listing-request-v1',
                    checkpoints=dict(region=entry))
    return root / 'release.json', manifest, entry


class ReleaseNullTest(unittest.TestCase):
    def test_declared_null_roles_are_invalid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, entry = release_fixture(Path(directory))
            with patch('card_condition.release.version', return_value='fixture-version'):
                for role in ('region', 'observation', 'recall'):
                    checkpoints = dict(region=entry)
                    checkpoints[role] = None
                    path.write_text(json.dumps(dict(manifest, checkpoints=checkpoints)))
                    with self.subTest(role=role), self.assertRaisesRegex(ValueError, role + ' checkpoint entry'):
                        read_release(path)

    def test_omitted_optional_roles_and_valid_declared_roles_keep_sha_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, entry = release_fixture(Path(directory))
            with patch('card_condition.release.version', return_value='fixture-version'):
                for checkpoints in (dict(region=entry), dict(region=entry, observation=entry, recall=entry)):
                    path.write_text(json.dumps(dict(manifest, checkpoints=checkpoints)))
                    info, files = read_release(path)
                    self.assertEqual(set(checkpoints), set(files))
                    self.assertEqual(set(checkpoints), set(info['checkpoint_sha256']))
                path.write_text(json.dumps(dict(manifest, checkpoints=dict(region=dict(entry, sha256='0'*64)))))
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    read_release(path)

    def test_cli_null_roles_return_existing_json_error_without_loading_models(self):
        from card_condition.cli import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, manifest, entry = release_fixture(root)
            request = root / 'request.json'
            request.write_text(json.dumps(dict(id='fixture')))
            with patch('card_condition.release.version', return_value='fixture-version'), \
                 patch('card_condition.listing_model.RegionAnalyzer') as region:
                for role in ('region', 'observation', 'recall'):
                    checkpoints = dict(region=entry)
                    checkpoints[role] = None
                    path.write_text(json.dumps(dict(manifest, checkpoints=checkpoints)))
                    out, err = io.StringIO(), io.StringIO()
                    argv = ['card-condition', 'listing-predict', str(request), '--release', str(path), '--device', 'cpu']
                    with patch('sys.argv', argv), redirect_stdout(out), redirect_stderr(err):
                        with self.assertRaises(SystemExit) as done:
                            main()
                    self.assertEqual(1, done.exception.code)
                    self.assertEqual('', out.getvalue())
                    error = json.loads(err.getvalue())
                    self.assertTrue(error['requires_gemini'])
                    self.assertIn(role + ' checkpoint entry', error['error'])
                region.assert_not_called()
