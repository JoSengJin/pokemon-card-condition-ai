import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import pilot_record
from card_condition.pilot_summary import read_lines

WRITE = os.write
ENTRY = dict(schema_version=1, kind='listing_predict_usage', outcome='ok', request_id='synthetic-fixture')


def partial_write(fd, line):
    return WRITE(fd, line[:len(line)//2])


class PilotShortWriteTest(unittest.TestCase):
    def test_short_write_is_durable_closed_and_rejected_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            with patch.object(pilot_record.os, 'write', side_effect=partial_write), \
                 patch.object(pilot_record.os, 'fsync', wraps=os.fsync) as sync, \
                 patch.object(pilot_record.os, 'close', wraps=os.close) as close:
                with self.assertRaisesRegex(OSError, 'not fully written'):
                    pilot_record.append_line(path, ENTRY)
                sync.assert_called_once()
                close.assert_called_once()
            self.assertTrue(path.read_bytes())
            self.assertFalse(path.read_bytes().endswith(b'\n'))
            with self.assertRaises(ValueError):
                read_lines(path, 'listing_predict_usage')

    def test_zero_byte_write_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            with patch.object(pilot_record.os, 'write', return_value=0):
                with self.assertRaisesRegex(OSError, 'not fully written'):
                    pilot_record.append_line(path, ENTRY)
            self.assertEqual(b'', path.read_bytes())

    def test_full_write_preserves_one_exact_json_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            pilot_record.append_line(path, ENTRY)
            self.assertEqual([ENTRY], read_lines(path, 'listing_predict_usage'))
            self.assertEqual((json.dumps(ENTRY, ensure_ascii=False, allow_nan=False)+'\n').encode(), path.read_bytes())

    def test_failed_finish_does_not_advance_completed_or_warm_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'usage.jsonl'
            recorder = pilot_record.UsageRecorder(path)
            recorder.start(dict(id='synthetic-fixture'))
            with patch.object(recorder, 'entry', return_value=ENTRY), \
                 patch.object(pilot_record.os, 'write', side_effect=partial_write):
                with self.assertRaisesRegex(OSError, 'not fully written'):
                    recorder.finish({})
            self.assertEqual(0, recorder.completed)
            self.assertIsNotNone(recorder.began)

    def test_cli_never_prints_success_after_short_log_write(self):
        from test_listing_review_whole_scope import manual_fixture
        from test_release import run_cli
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_path, request_path, report, decisions = manual_fixture(root)
            report.update(device='cpu', image_size=224, batched_views=False)
            log = root/'usage.jsonl'
            with patch('card_condition.listing_model.ListingAnalyzer') as model, \
                 patch.object(pilot_record.os, 'write', side_effect=partial_write):
                model.return_value.analyze.return_value = report
                code, out, err = run_cli([str(root/'not-loaded.pt'), str(request_path), '--usage-log', str(log)])
            self.assertEqual((1, ''), (code, out))
            error = json.loads(err)
            self.assertTrue(error['requires_gemini'])
            self.assertIn('not fully written', error['error'])
            model.return_value.analyze.assert_called_once()
            with self.assertRaises(ValueError):
                read_lines(log, 'listing_predict_usage')
