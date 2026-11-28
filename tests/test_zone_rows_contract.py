"""The rater gate (T3) and zone_rows (T1) must read the same answer file; an incomplete comparison must be visible."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import zone_rows

LINE = 'a/back=확인;box:0,0,1,1;upper_left:미확인'


def run(answer_bytes, **provenance):
    with tempfile.TemporaryDirectory() as t:
        answer, record = Path(t, 'answer.txt'), Path(t, 'p.json')
        answer.write_bytes(answer_bytes)
        record.write_text(json.dumps(dict(verdict='unknown', answer_sha256=hashlib.sha256(answer_bytes).hexdigest(), **provenance)))
        err = io.StringIO()
        with mock.patch.object(zone_rows, 'backs', return_value={'a': ('unused.png', 'intake')}), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = zone_rows.main([str(answer), '--kind', 'corner', '--box', 'confirmed-only', '--out', f'{t}/out',
                                   '--provenance', str(record)])
    return code, err.getvalue()


class Contract(unittest.TestCase):
    def test_extraction_copy_with_comment_and_bom_is_read(self):
        code, err = run(('﻿# 원문sha256=' + '0' * 64 + '\n# 화면=A\n' + LINE + '\n').encode(), comparison_complete=True)
        self.assertEqual((code, err), (0, ''))

    def test_incomplete_or_unrecorded_comparison_is_announced_and_changes_no_rows(self):
        for provenance in ({'comparison_complete': False, 'incomplete': [{'path': 'x'}]}, {}):
            with self.subTest(provenance=provenance):
                code, err = run(LINE.encode(), **provenance)
                self.assertEqual(code, 0)
                self.assertIn('AI 대조가 완전하다고 기록되지 않음', err)

    def test_comment_only_difference_gives_same_answers(self):
        self.assertEqual([a['states'] for a in zone_rows.parse('# memo\n' + LINE)], [a['states'] for a in zone_rows.parse(LINE)])
        with self.assertRaises(ValueError):
            zone_rows.parse(LINE + ' # tail')


if __name__ == '__main__':
    unittest.main()
