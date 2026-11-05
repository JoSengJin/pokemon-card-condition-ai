import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import io
from contextlib import redirect_stdout

from card_condition import back_triage_cli as cli
from card_condition.back_triage_release import CONTRACT, PARTS, read_release, sha256, tree_sha256


def make_release(folder, **change):
    root = Path(folder)
    heads = {}
    for p in PARTS:
        (root/f'{p}.pt').write_bytes(p.encode())
        heads[p] = dict(file=f'{p}.pt', sha256=sha256(root/f'{p}.pt'))
    (root/'w.pth').write_bytes(b'w')
    (root/'hub').mkdir(exist_ok=True)
    (root/'hub'/'hubconf.py').write_text('x=1')
    m = dict(release_id='r', package_version='0.6.0', input_contract=CONTRACT, heads=heads,
             backbone=dict(weights=dict(file='w.pth', sha256=sha256(root/'w.pth')), hub_dir=dict(file='hub', sha256=tree_sha256(root/'hub'))))
    m.update(change)
    (root/'release.json').write_text(json.dumps(m))
    return root/'release.json'


@mock.patch('card_condition.back_triage_release.version', return_value='0.6.0')
class ReleaseTest(unittest.TestCase):
    def test_valid_release_reads(self, _):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual('r', read_release(make_release(d))['release_id'])

    def test_every_tamper_is_rejected(self, _):
        with tempfile.TemporaryDirectory() as d:
            path = make_release(d)
            for victim in ('edge.pt', 'w.pth'):
                (Path(d)/victim).write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError, 'checksum_mismatch'):
                    read_release(path)
                make_release(d)
            (Path(d)/'hub'/'hubconf.py').write_text('x=2')
            with self.assertRaisesRegex(ValueError, 'checksum_mismatch:backbone_hub'):
                read_release(path)
            make_release(d)
            (Path(d)/'corner.pt').unlink()
            with self.assertRaisesRegex(ValueError, 'checksum_mismatch'):
                read_release(path)

    def test_contract_version_and_keys_are_enforced(self, _):
        with tempfile.TemporaryDirectory() as d:
            for change in (dict(input_contract='other'), dict(extra=1)):
                with self.assertRaisesRegex(ValueError, 'release_manifest_invalid'):
                    read_release(make_release(d, **change))
        with tempfile.TemporaryDirectory() as d, mock.patch('card_condition.back_triage_release.version', return_value='0.5.0'):
            with self.assertRaisesRegex(ValueError, 'package_version_mismatch'):
                read_release(make_release(d))


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(args))
        return code, json.loads(out.getvalue())

    def test_bad_request_and_unavailable_release_are_explicit_holds(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d)/'bad.json'
            bad.write_text('{"id": "x"}')
            code, out = self.run_cli('--release', str(Path(d)/'none.json'), '--request', str(bad))
            self.assertEqual((3, 'held', 'request_contract_violation', 'existing_path'), (code, out['status'], out['reason'], out['fallback']))
            good = Path(d)/'good.json'
            good.write_text(json.dumps(dict(id='x', side='back', image='a.png', box=[0, 0, 1, 1], box_reviewed=True)))
            code, out = self.run_cli('--release', str(Path(d)/'none.json'), '--request', str(good))
            self.assertEqual((2, 'held'), (code, out['status']))
            self.assertTrue(out['reason'].startswith('release_unavailable'))
            self.assertFalse(out['complete'])
            code, out = self.run_cli('--release', 'x', '--request', str(Path(d)/'missing.json'))
            self.assertEqual((3, 'request_unreadable'), (code, out['reason']))


if __name__ == '__main__':
    unittest.main()
