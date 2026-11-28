"""Combination table for phone AI lines (2026-11-28). Expectations were written by hand before the parser change.

Priority per zone: a value from a clean line wins; damaged lines only fill zones no clean line has; a zone nobody could
read is covered but never matches, never conflicts and never proves 'no match'.
"""
import unittest

from tests.test_rater_gate import RaterGateBase

AREAS = [f'c{n}' for n in range(9)]
STATES = ['정상', '결함', '정상', '정상', '결함', '정상', '정상', '정상', '결함']
HEAD = 'a/back=확인;box:0,0,1,1;'


def line(states=STATES, areas=AREAS):
    return HEAD + ';'.join(f'{a}:{s}' for a, s in zip(areas, states))


C, CX = line(), line(['미확인'] * 9)                          # clean copy, clean different values
DP = C.replace('c3:정상', 'c3:정상:흐림')                      # damaged copy: one zone unreadable
DT, DX = C + ';', CX + ';'                                   # damaged copy / damaged different values
N = HEAD + ';'.join(AREAS)                                   # no zone readable
SAME, SUSPECT, NO, UNKNOWN = 'ai_identical', 'ai_suspect', 'no_match_found', 'unknown'
# lines of one AI file: (verdict as .txt, verdict as .log, (matches, total) or None, any damaged or conflicting line)
TABLE = {
    (C,): (SAME, SAME, (9, 9), False), (CX,): (NO, NO, (0, 9), False), (C, C): (SAME, SAME, (9, 9), False),
    (DP,): (SUSPECT, SUSPECT, (8, 9), True), (DT,): (SAME, SAME, (9, 9), True),
    (DX,): (UNKNOWN, NO, (0, 9), True), (N,): (UNKNOWN, NO, (0, 9), True),
    (DP, C): (SAME, SAME, (9, 9), True), (C, DP): (SAME, SAME, (9, 9), True),
    (DX, C): (SAME, SAME, (9, 9), True), (C, DX): (SAME, SAME, (9, 9), True),
    (N, C): (SAME, SAME, (9, 9), True), (C, N): (SAME, SAME, (9, 9), True),
    (DP, CX): (UNKNOWN, NO, (0, 9), True), (CX, DT): (UNKNOWN, NO, (0, 9), True),   # known limit: clean line wins
    (C, CX): (UNKNOWN, NO, None, True), (C, CX, DT): (UNKNOWN, NO, None, True),     # a clean conflict is never refilled
    (DP, DT): (SAME, SAME, (9, 9), True), (DT, DP): (SAME, SAME, (9, 9), True), (N, DT): (SAME, SAME, (9, 9), True),
    (DT, DX): (UNKNOWN, NO, None, True),
}


class RaterGateTableTest(RaterGateBase):
    def prepare(self):
        self.answer.write_text(C + '\n', encoding='utf-8')
        (self.root / 'said.txt').write_text('직접 판정', encoding='utf-8')
        return ['--statement', str(self.root / 'said.txt'), '--expected', str(self.root / 'said.txt')]

    def outcome(self, name, lines, extra):
        path = self.root / 'ai-responses' / name
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        result = self.run_gate(*extra)[1]
        path.unlink()
        found = [(r['matches'], r['total']) for r in result['comparisons'] if r['path'].endswith('/' + name)]
        return result['verdict'], found[0] if found else None, result['comparison_complete']

    def test_table_beside_an_unrelated_clean_file(self):
        extra = self.prepare()
        (self.root / 'ai-responses/unrelated.txt').write_text(CX + '\n', encoding='utf-8')
        for number, (lines, (as_txt, as_log, found, damaged)) in enumerate(TABLE.items()):
            for suffix, verdict, complete in (('txt', as_txt, not damaged), ('log', as_log, True)):
                with self.subTest(row=number, suffix=suffix):
                    self.assertEqual(self.outcome(f'ai.{suffix}', lines, extra), (verdict, found, complete))

    def test_unread_zones_are_not_a_basis_for_no_match(self):
        extra = self.prepare()
        for name, lines, verdict in (('run.log', (N,), UNKNOWN), ('run.log', (DP,), SUSPECT), ('ai.txt', (N,), UNKNOWN),
                                     ('run.log', (N.replace('c0;', 'c0:12:00;'),), UNKNOWN), ('run.log', (CX,), NO)):
            with self.subTest(name=name, line=lines[0][:40]):
                self.assertEqual(self.outcome(name, lines, extra)[0], verdict)

    def test_typo_zone_drops_only_itself_and_second_card_is_not_attributed(self):
        extra = self.prepare()
        for body, found in ((C.replace('c4:결함', 'c4=결함'), (8, 8)), (C.replace('c4:결함', 'c4：＝결함'), (8, 8)),
                            (C.replace(';c4:', ';b/back=확인;c4:'), (4, 4)),
                            ('a/back=확인;box:0,0,1,1 b/back=확인;c1:결함', None)):
            with self.subTest(body=body[:60]):
                self.assertEqual(self.outcome('ai.txt', (body,), extra), (UNKNOWN, found, False))

    def test_human_answer_with_any_damaged_or_conflicting_line_is_refused(self):
        for lines in ((DP,), (DT,), (N,), (C, DT), (C, CX), ('a/back=확인;box:0,0,1,1 b/back=확인;c1:결함',)):
            with self.subTest(lines=lines[-1][:50]):
                self.answer.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                self.assertEqual(self.run_gate(), (2, None))
        self.answer.write_text(C + '\n' + C + '\n', encoding='utf-8')
        self.assertEqual(self.run_gate()[0], 0)


if __name__ == '__main__':
    unittest.main()
