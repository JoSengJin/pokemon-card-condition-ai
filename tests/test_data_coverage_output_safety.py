import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition.data_coverage import data_coverage


class DataCoverageOutputSafetyTest(unittest.TestCase):
    def test_complete_report_is_published_and_temporary_file_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            result = {'complete': True, 'note': '감사'}
            with patch('card_condition.data_coverage.coverage_report', return_value=result):
                self.assertEqual(result, data_coverage('unused', output))
            self.assertEqual(result, json.loads(output.read_text()))
            self.assertEqual([output], list(Path(folder).iterdir()))

    def test_partial_write_is_removed_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            def broken_dump(result, stream, **kwargs):
                stream.write('{"partial":')
                raise OSError('simulated disk full')
            with patch('card_condition.data_coverage.coverage_report', return_value={'complete': True}):
                with patch('card_condition.data_coverage.json.dump', side_effect=broken_dump):
                    with self.assertRaisesRegex(OSError, 'disk full'):
                        data_coverage('unused', output)
                self.assertEqual([], list(Path(folder).iterdir()))
                data_coverage('unused', output)
            self.assertEqual({'complete': True}, json.loads(output.read_text()))

    def test_sync_failure_leaves_no_report_or_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('card_condition.data_coverage.coverage_report', return_value={}), patch(
                    'card_condition.data_coverage.os.fsync', side_effect=OSError('sync failed')):
                with self.assertRaisesRegex(OSError, 'sync failed'):
                    data_coverage('unused', output)
            self.assertEqual([], list(Path(folder).iterdir()))

    def test_publish_failure_leaves_no_report_or_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('card_condition.data_coverage.coverage_report', return_value={}), patch(
                    'card_condition.data_coverage.os.link', side_effect=OSError('link unavailable')):
                with self.assertRaisesRegex(OSError, 'link unavailable'):
                    data_coverage('unused', output)
            self.assertEqual([], list(Path(folder).iterdir()))

    def test_existing_report_is_preserved_without_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            output.write_bytes(b'existing report')
            with patch('card_condition.data_coverage.coverage_report') as audit:
                with self.assertRaisesRegex(ValueError, 'Output exists'):
                    data_coverage('unused', output)
                audit.assert_not_called()
            self.assertEqual(b'existing report', output.read_bytes())
            self.assertEqual([output], list(Path(folder).iterdir()))

    def test_competing_report_is_preserved_during_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            real_link = os.link
            def competing_link(source, destination):
                output.write_bytes(b'competing report')
                real_link(source, destination)
            with patch('card_condition.data_coverage.coverage_report', return_value={}), patch(
                    'card_condition.data_coverage.os.link', side_effect=competing_link):
                with self.assertRaises(FileExistsError):
                    data_coverage('unused', output)
            self.assertEqual(b'competing report', output.read_bytes())
            self.assertEqual([output], list(Path(folder).iterdir()))
