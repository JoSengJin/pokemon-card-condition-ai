"""Command line, output publishing and failure behaviour of the standalone validator CLI."""
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
from card_condition import side_evidence_cli as cli
from card_condition.side_evidence import validate_sidecar
from test_side_evidence_sources import Fixture

ROOT = Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.f = Fixture(self.temp.name)
        self.sidecar = self.f.save(self.f.sidecar())
        self.out_dir = self.f.folder / 'reports'
        self.out_dir.mkdir()
        self.output = self.out_dir / 'report.json'

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, output=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ['--sidecar', str(self.sidecar), '--evidence-root', str(self.f.root), '--output', str(output or self.output)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def leftovers(self):
        return sorted(p.name for p in self.out_dir.iterdir() if p.name != 'report.json')

    def test_writes_new_report_and_preserves_inputs(self):
        before = self.f.snapshot()
        code, stdout, stderr = self.run_main()
        self.assertEqual((0, ''), (code, stderr))
        self.assertEqual('side-evidence: accepted 3 rows\n', stdout)
        self.assertEqual(before, {k: v for k, v in self.f.snapshot().items() if not k.startswith(str(self.out_dir))})
        self.assertEqual(validate_sidecar(self.sidecar, self.f.root), json.loads(self.output.read_text()))
        self.assertNotIn(str(self.f.folder), self.output.read_text())
        self.assertEqual([], self.leftovers())

    def test_rejected_sidecar_exits_1_without_output(self):
        self.f.write('inventory.json', dict(latest=[]))
        code, stdout, stderr = self.run_main()
        self.assertEqual((1, ''), (code, stdout))
        self.assertRegex(stderr, r'^side-evidence: rejected: R1: [^\n]*\n$')
        self.assertFalse(self.output.exists())
        self.assertEqual([], self.leftovers())

    def test_usage_error_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(['--sidecar', str(self.sidecar)])
        self.assertEqual(2, raised.exception.code)

    def test_existing_output_is_never_replaced(self):
        self.output.write_text('keep')
        code, _, stderr = self.run_main()
        self.assertEqual(3, code)
        self.assertEqual('keep', self.output.read_text())
        self.assertNotIn(str(self.f.folder), stderr)
        self.assertEqual(1, stderr.count('\n'))

    def test_competing_output_created_during_validation_is_preserved(self):
        def compete(*args):
            report = validate_sidecar(*args)
            self.output.write_text('competitor')
            return report
        with patch.object(cli, 'validate_sidecar', compete):
            code, _, stderr = self.run_main()
        self.assertEqual(3, code)
        self.assertIn('FileExistsError', stderr)
        self.assertEqual('competitor', self.output.read_text())
        self.assertEqual([], self.leftovers())

    def test_partial_write_failure_leaves_no_file_and_can_retry(self):
        real_dump = json.dump
        def partial(value, stream, **kwargs):
            stream.write('{"schema": ')
            raise OSError(errno.ENOSPC, 'No space left on device')
        with patch.object(cli.json, 'dump', partial):
            code, _, stderr = self.run_main()
        self.assertEqual(3, code)
        self.assertIn('No space left on device', stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual([], self.leftovers())
        self.assertIs(real_dump, json.dump)
        self.assertEqual(0, self.run_main()[0])
        self.assertEqual(validate_sidecar(self.sidecar, self.f.root), json.loads(self.output.read_text()))

    def test_unsupported_hard_link_publishes_nothing(self):
        with patch.object(cli.os, 'link', side_effect=OSError(errno.EPERM, 'Operation not permitted')):
            code, _, stderr = self.run_main()
        self.assertEqual(3, code)
        self.assertIn('Operation not permitted', stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual([], self.leftovers())

    def test_missing_output_folder_or_root_are_file_errors(self):
        self.assertEqual(3, self.run_main(self.f.folder / 'absent' / 'report.json')[0])
        argv = ['--sidecar', str(self.sidecar), '--evidence-root', str(self.f.folder / 'nowhere'), '--output', str(self.output)]
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(3, cli.main(argv))
        self.assertIn('NotADirectoryError', stderr.getvalue())
        self.assertFalse(self.output.exists())

    def test_module_entry_point(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        command = [sys.executable, '-m', 'card_condition.side_evidence_cli', '--sidecar', str(self.sidecar),
                   '--evidence-root', str(self.f.root), '--output', str(self.output)]
        done = subprocess.run(command, cwd=self.f.folder, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((0, ''), (done.returncode, done.stderr))
        again = subprocess.run(command, cwd=self.f.folder, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(3, again.returncode)
        self.assertEqual(1, again.stderr.count('\n'))


if __name__ == '__main__':
    unittest.main()
