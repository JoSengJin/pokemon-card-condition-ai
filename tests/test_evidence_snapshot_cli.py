"""Snapshot CLI wiring, output preservation and failure cleanup; synthetic files only."""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from card_condition import evidence_snapshot_cli as cli
from card_condition import side_evidence_cli, side_evidence_prepare
from card_condition.evidence_snapshot import audit_snapshot
from test_evidence_snapshot import Snapshot

ROOT = Path(__file__).resolve().parents[1]


class SnapshotCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Snapshot(self.temp.name)
        self.out = self.s.folder / 'reports'
        self.out.mkdir()
        self.output = self.out / 'audit.json'

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, module=cli, argv=None):
        argv = argv or ['--index', str(self.s.index), '--evidence-root', str(self.s.root), '--output', str(self.output)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def inputs(self):
        return {k: v for k, v in self.s.snapshot().items() if not k.startswith(str(self.out))}

    def leftovers(self):
        return sorted(p.name for p in self.out.iterdir() if p.name != self.output.name)

    def test_writes_the_audit_and_preserves_inputs(self):
        before = self.inputs()
        code, stdout, stderr = self.run_main()
        self.assertEqual((0, 'evidence-snapshot: verified 3 payloads (integrity only)\n', ''), (code, stdout, stderr))
        self.assertEqual(audit_snapshot(self.s.index, self.s.root), json.loads(self.output.read_text()))
        self.assertEqual(before, self.inputs())
        self.assertNotIn(str(self.s.folder), self.output.read_text())
        self.assertEqual([], self.leftovers())

    def test_rejected_snapshot_exits_1_without_output(self):
        (self.s.root / 'sources/artifacts/intake/REPORT.md').write_text('changed\n')
        code, stdout, stderr = self.run_main()
        self.assertEqual((1, ''), (code, stdout))
        self.assertRegex(stderr, r'^evidence-snapshot: rejected: S: [^\n]*\n$')
        self.assertFalse(self.output.exists())

    def test_usage_error_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(['--index', str(self.s.index)])
        self.assertEqual(2, raised.exception.code)

    def test_existing_and_competing_outputs_are_preserved(self):
        self.output.write_text('keep')
        code, _, stderr = self.run_main()
        self.assertEqual((3, 'keep'), (code, self.output.read_text()))
        self.assertNotIn(str(self.s.folder), stderr)
        self.output.unlink()
        def compete(*args):
            report = audit_snapshot(*args)
            self.output.write_text('competitor')
            return report
        with patch.object(cli, 'audit_snapshot', compete):
            code, _, stderr = self.run_main()
        self.assertEqual((3, 'competitor'), (code, self.output.read_text()))
        self.assertIn('FileExistsError', stderr)
        self.assertEqual([], self.leftovers())

    def test_write_flush_and_link_failures_leave_nothing_and_retry_works(self):
        failures = (patch.object(side_evidence_cli.json, 'dump', side_effect=OSError(errno.ENOSPC, 'No space left on device')),
                    patch.object(side_evidence_cli.os, 'fsync', side_effect=OSError(errno.EIO, 'Input/output error')),
                    patch.object(side_evidence_cli.os, 'link', side_effect=OSError(errno.EPERM, 'Operation not permitted')))
        for failure in failures:
            with failure:
                code, _, stderr = self.run_main()
            self.assertEqual(3, code)
            self.assertEqual(1, stderr.count('\n'))
            self.assertFalse(self.output.exists())
            self.assertEqual([], self.leftovers())
        self.assertEqual(0, self.run_main()[0])

    def test_prepare_cli_uses_the_same_publisher(self):
        output = self.out / 'sidecar.json'
        argv = ['--inventory', 'sources/artifacts/intake/inventory.json', '--evidence-root', str(self.s.root),
                '--rows-pointer', '/latest', '--output', str(output)]
        with patch.object(side_evidence_cli.os, 'link', side_effect=OSError(errno.EPERM, 'Operation not permitted')):
            self.assertEqual(3, self.run_main(side_evidence_prepare, argv)[0])
        self.assertEqual([], sorted(p.name for p in self.out.iterdir()))
        self.assertEqual(0, self.run_main(side_evidence_prepare, argv)[0])

    def test_module_entry_points(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        audit = [sys.executable, '-m', 'card_condition.evidence_snapshot_cli', '--index', str(self.s.index),
                 '--evidence-root', str(self.s.root), '--output', str(self.output)]
        done = subprocess.run(audit, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((0, ''), (done.returncode, done.stderr))
        again = subprocess.run(audit, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((3, 1), (again.returncode, again.stderr.count('\n')))
        prepare = [sys.executable, '-m', 'card_condition.side_evidence_prepare', '--inventory',
                   'sources/artifacts/intake/inventory.json', '--evidence-root', str(self.s.root), '--rows-pointer', '/latest',
                   '--output', str(self.out / 'sidecar.json')]
        done = subprocess.run(prepare, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((0, ''), (done.returncode, done.stderr))


if __name__ == '__main__':
    unittest.main()
