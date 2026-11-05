from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
from importlib.metadata import version
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import torch
from torch import nn

from card_condition.cli import main
from card_condition.listing_model import ListingAnalyzer
from card_condition.regions import REGION_LABELS
from card_condition.side_model import backbone_for


def fixture_release(root, seed=0, **changes):
    """Random-init synthetic region checkpoint plus a pinned manifest; not a quality model."""
    torch.manual_seed(seed)
    backbone, dimension = backbone_for('mobilenet_v3_small')
    checkpoint = root/f'region-{seed}.pt'
    torch.save(dict(architecture='mobilenet_v3_small_region_v1', labels=list(REGION_LABELS),
                    supported=['surface_defect'], image_size=224, backbone=backbone.state_dict(),
                    head=nn.Linear(dimension, len(REGION_LABELS)).state_dict()), checkpoint)
    Image.new('RGB', (96, 128), (seed * 40 % 255, 120, 200)).save(root/'photo.png')
    (root/'request.json').write_text(json.dumps(dict(id='one', front=dict(
        image=str(root/'photo.png'), box=[.05, .05, .95, .95], visibility_issues=[]))))
    manifest = dict(release_id=f'fixture-{seed}', package_version=version('pokemon-card-condition'),
                    input_contract='listing-request-v1',
                    checkpoints=dict(region=dict(file=checkpoint.name,
                                                 sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())))
    manifest.update(changes)
    (root/'release.json').write_text(json.dumps(manifest))
    return root/'release.json', checkpoint


def run_cli(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with patch('sys.argv', ['card-condition', 'listing-predict', *argv, '--device', 'cpu']), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            main()
        except SystemExit as exc:
            code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()


class ReleaseTest(unittest.TestCase):
    def test_release_runs_pinned_checkpoint_and_identifies_release(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest, checkpoint = fixture_release(Path(folder))
            request = json.loads((Path(folder)/'request.json').read_text())
            report = ListingAnalyzer(release=manifest, device='cpu').analyze(request)
            digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            self.assertEqual(digest, report['model_sha256'])
            self.assertEqual(dict(release_id='fixture-0', package_version=version('pokemon-card-condition'),
                input_contract='listing-request-v1', checkpoint_sha256=dict(region=digest),
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()), report['release'])
            self.assertGreater(report['inferred_regions'], 0)
            self.assertIn('centering_not_evaluated', report['listing_readiness']['records'][0]['whole_listing_blockers'])
            self.assertFalse(report['production_ready'])
            direct = ListingAnalyzer(str(checkpoint), 'cpu').analyze(request)
            self.assertNotIn('release', direct)
            self.assertEqual(direct['predictions'], report['predictions'])

    def test_mismatched_release_is_rejected_before_loading_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, checkpoint = fixture_release(root)
            entry = dict(file=checkpoint.name, sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
            cases = {'SHA256 mismatch': dict(checkpoints=dict(region=dict(entry, sha256='0'*64))),
                     'package version': dict(package_version='0.0.1'),
                     'input contract': dict(input_contract='listing-request-v0'),
                     'region checkpoint entry': dict(checkpoints=dict(region=dict(entry, file=str(checkpoint)))),
                     'Invalid release manifest': dict(checkpoints=dict(region=entry, extra=entry))}
            with patch('card_condition.listing_model.RegionAnalyzer') as region:
                for message, change in cases.items():
                    manifest, _ = fixture_release(root, **change)
                    with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                        ListingAnalyzer(release=manifest, device='cpu')
                with self.assertRaisesRegex(ValueError, 'not both'):
                    ListingAnalyzer(str(checkpoint), release=fixture_release(root)[0])
                region.assert_not_called()

    def test_checkpoint_swapped_during_load_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest, _ = fixture_release(Path(folder))
            with patch('card_condition.listing_model.RegionAnalyzer') as region:
                region.return_value.model_sha256 = 'f'*64
                with self.assertRaisesRegex(ValueError, 'differs from release'):
                    ListingAnalyzer(release=manifest, device='cpu')

    def test_cli_release_success_failure_and_direct_compatibility(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, checkpoint = fixture_release(root)
            request = str(root/'request.json')
            code, stdout, _ = run_cli([request, '--release', str(manifest)])
            self.assertEqual(0, code)
            self.assertEqual('fixture-0', json.loads(stdout)['release']['release_id'])
            code, stdout, _ = run_cli([str(checkpoint), request])
            self.assertEqual(0, code)
            self.assertNotIn('release', json.loads(stdout))
            for argv in ([request], [str(checkpoint), request, '--release', str(manifest)]):
                code, stdout, stderr = run_cli(argv)
                self.assertEqual((1, ''), (code, stdout))
                self.assertTrue(json.loads(stderr)['requires_gemini'])
            checkpoint.write_bytes(b'corrupt')
            manifest, _ = fixture_release(root, checkpoints=dict(region=dict(
                file=checkpoint.name, sha256=hashlib.sha256(b'corrupt').hexdigest())))
            checkpoint.write_bytes(b'corrupt')
            code, stdout, stderr = run_cli([request, '--release', str(manifest)])
            self.assertEqual((1, ''), (code, stdout))
            self.assertEqual('Invalid or incomplete checkpoint; use Gemini fallback', json.loads(stderr)['error'])


if __name__ == '__main__':
    unittest.main()
