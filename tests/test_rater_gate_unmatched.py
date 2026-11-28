"""A file that points at the answer but is not compared as written must never support 'no match'.

Metamorphic relation: noise that keeps the NFKC/casefold/alphanumeric form of an exact AI copy never yields
no_match_found, even with a clean unrelated AI file beside it.
"""
import tempfile
import unittest
from pathlib import Path

from tools.rater_gate import chance, compare, verdict
from tools.rater_gate_lines import values

LINE = 'abc12/back=확인;box:0.1,0.1,0.9,0.9;top_left:정상;top_right:결함'
OTHER = 'abc12/back=확인;box:0.1,0.1,0.9,0.9;top_left:결함;top_right:정상'  # clean file that agrees nowhere
ANSWER = values(LINE)
NOISE = (' ', '\t', '*', '-', '.', ',', '"', "'", '`', '|', '>', '_', ':', ';', '=', '/', '#', '　', '​')


def judge(files):
    with tempfile.TemporaryDirectory() as folder:
        for name, text in files.items():
            Path(folder, name).write_text(text, encoding='utf-8')
        records, _, incomplete, _ = compare(ANSWER, [Path(folder)], 0, None)
    return verdict(records, chance(ANSWER), True, incomplete), records, incomplete


class Unmatched(unittest.TestCase):
    def test_reproduced_variants_are_unknown(self):
        variants = ['* ' + LINE, '1. ' + LINE, '답: ' + LINE, '**' + LINE + '**', LINE.replace(';top', '; top'),
                    LINE.replace('정상;', '정상 ;'), LINE.replace('abc12', 'ABC12'), LINE.replace('abc12/back', 'abc12 / back'),
                    LINE.replace('결함', '결함.'), '# ' + LINE]
        for copy in variants:
            with self.subTest(copy=copy):
                self.assertEqual(judge({'other.txt': OTHER, 'copy.txt': copy})[0], 'unknown')

    def test_canon_preserving_noise_never_gives_no_match(self):
        bad = []
        for noise in NOISE:
            for at in range(len(LINE) + 1):
                copy = LINE[:at] + noise + LINE[at:]
                if judge({'other.txt': OTHER, 'copy.txt': copy})[0] == 'no_match_found':
                    bad.append((noise, at))
        for copy in (LINE.upper(), LINE.title()):
            if judge({'other.txt': OTHER, 'copy.txt': copy})[0] == 'no_match_found':
                bad.append(copy)
        self.assertEqual(bad, [])

    def test_clean_and_unrelated_files_still_give_no_match(self):
        for extra in ({}, {'next.txt': LINE.replace('abc12', 'zzz99')},
                      {'edge.txt': 'abc12/back=확인;box:0.1,0.1,0.9,0.9;left:정상;right:결함'},
                      {'trace.log': '* ' + LINE}):  # .log keeps its existing exemption
            with self.subTest(extra=extra):
                self.assertEqual(judge({'other.txt': OTHER, **extra})[0], 'no_match_found')

    def test_records_and_flags_are_unchanged(self):
        result, records, incomplete = judge({'copy.txt': LINE})
        self.assertEqual((result, records[0]['matches'], incomplete), ('ai_identical', 2, []))
        result, records, _ = judge({'copy.txt': LINE, 'mangled.txt': '* ' + LINE})
        self.assertEqual((result, sorted(r['matches'] for r in records)), ('ai_identical', [0, 2]))


if __name__ == '__main__':
    unittest.main()
