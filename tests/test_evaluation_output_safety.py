"""A report is published whole or not at all; existing and competing outputs are never replaced."""
import errno
import json
import math
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_evaluation_consistency_contract import KINDS, Rewrite
from test_evaluation_inputs import evaluate, evaluation_fixture


class OutputSafetyTest(unittest.TestCase):
    def build(self, kind, module, constructor):
        """One mock evaluation fixture whose temporary folder is removed when the test ends."""
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
        method = analyzer.analyze if kind == 'region' else analyzer.predict
        return SimpleNamespace(kind=kind, module=module, constructor=constructor, root=root, manifest=manifest,
                               history=history, checkpoint=checkpoint, rows=rows, analyzer=analyzer, method=method,
                               output=root / 'out.json')

    def run_eval(self, setup, output=None):
        with patch.object(setup.module, setup.constructor, return_value=setup.analyzer) as loader:
            setup.loader = loader
            return evaluate(setup.kind, setup.module, setup.manifest, setup.history, setup.checkpoint, output or setup.output)

    def test_saved_json_is_exactly_the_returned_report(self):
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind):
                setup = self.build(kind, module, constructor)
                report = self.run_eval(setup)
                expected = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
                self.assertEqual(expected, setup.output.read_text(encoding='utf-8'))
                self.assertEqual((False, 0, True), (report['production_ready'], report['actual_calls_saved'], report['requires_gemini']))

    def test_failure_while_writing_leaves_no_report_and_the_retry_succeeds(self):
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind):
                setup = self.build(kind, module, constructor)
                before = sorted(os.listdir(setup.root))
                good = setup.method.return_value
                # A NaN probability makes the real json.dump fail after it has already written part of the report.
                setup.method.return_value = ({**good, 'probabilities': {**good['probabilities'], 'corner_defect': math.nan}}
                                             if kind == 'region' else {**good, 'corner_defect': math.nan})
                with self.assertRaises(ValueError):
                    self.run_eval(setup)
                self.assertFalse(setup.output.exists())
                self.assertEqual(before, sorted(os.listdir(setup.root)))
                with patch.object(json, 'dump', side_effect=OSError(errno.ENOSPC, 'No space left on device')):
                    with self.assertRaises(OSError):
                        self.run_eval(setup)
                self.assertFalse(setup.output.exists())
                self.assertEqual(before, sorted(os.listdir(setup.root)))
                setup.method.return_value = good
                self.assertEqual(self.run_eval(setup), json.loads(setup.output.read_text(encoding='utf-8')))

    def test_existing_output_is_refused_before_any_work_and_inputs_cannot_be_replaced(self):
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind):
                setup = self.build(kind, module, constructor)
                setup.output.write_text('keep')
                targets = [setup.output, setup.manifest, setup.history, setup.checkpoint, Path(setup.rows[4]['front'])]
                before = [path.read_bytes() for path in targets]
                for path in targets:
                    with self.assertRaisesRegex(ValueError, 'Output exists'):
                        self.run_eval(setup, path)
                    setup.loader.assert_not_called()
                os.symlink(setup.root / 'nowhere.json', setup.root / 'dangling.json')
                with self.assertRaises(FileExistsError):
                    self.run_eval(setup, setup.root / 'dangling.json')
                self.assertFalse((setup.root / 'nowhere.json').exists())
                self.assertEqual(before, [path.read_bytes() for path in targets])

    def test_competing_output_created_during_the_run_is_preserved(self):
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind):
                setup = self.build(kind, module, constructor)
                # unchanged_inputs runs right before saving; the competitor appears just ahead of it.
                with patch.object(module, 'unchanged_inputs', Rewrite(setup.output, b'competitor', module.unchanged_inputs)):
                    with self.assertRaises(FileExistsError):
                        self.run_eval(setup)
                self.assertEqual('competitor', setup.output.read_text())
                self.assertEqual([], [name for name in os.listdir(setup.root) if name.startswith('.')])

    def test_publisher_survives_sync_and_link_failures_without_clobbering(self):
        from card_condition.evaluation_output import write_new_report
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        output = folder / 'report.json'
        for target in ('os.fsync', 'os.link'):
            with patch(target, side_effect=OSError(errno.EIO, 'Input/output error')), self.assertRaises(OSError):
                write_new_report(output, {'ok': 1})
            self.assertEqual([], os.listdir(folder))
        output.write_text('competitor')
        with self.assertRaises(FileExistsError):
            write_new_report(output, {'ok': 1})
        self.assertEqual((['report.json'], 'competitor'), (os.listdir(folder), output.read_text()))


if __name__ == '__main__':
    unittest.main()
