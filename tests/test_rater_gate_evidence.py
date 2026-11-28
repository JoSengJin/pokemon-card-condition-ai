"""Evidence completeness (2026-11-28): what was not fully compared is never reported as 'no match', and evidence is kept."""
import random
import unittest

from tests.test_rater_gate import VALUES, RaterGateBase, text
from tools import rater_gate


class RaterGateEvidenceTest(RaterGateBase):
    def confirmed(self):
        (self.root / 'said.txt').write_text('직접 판정', encoding='utf-8')
        rng = random.Random(2)
        self.ai('unrelated.txt', [rng.choice(VALUES) for _ in range(64)])
        return ['--statement', str(self.root / 'said.txt'), '--expected', str(self.root / 'said.txt')]

    def judged(self, name, body, extra):
        path = self.root / 'ai-responses' / name
        path.write_bytes(body if isinstance(body, bytes) else body.encode())
        result = self.run_gate(*extra)[1]
        path.unlink()
        found = [(r['matches'], r['total']) for r in result['comparisons'] if r['path'].endswith('/' + name)]
        return result['verdict'], found[0] if found else None, result

    def test_unread_lines_block_no_match_and_keep_evidence(self):
        extra, copy = self.confirmed(), text(self.mine)
        for name, body in (('bullet.txt', '- ' + copy), ('merged.txt', copy.replace('\nz2=', ' z2=', 1)),
                           ('conflict.txt', copy + 'z1=정정\n'), ('note.txt', '설명 한 줄\n' + text(self.mine[:5])),
                           ('phone.txt', '- a/back=확인;box:0,0,1,1;upper_left:정상\n' + text(self.mine[:3]))):
            with self.subTest(name=name):
                verdict, found, result = self.judged(name, body, extra)
                self.assertIsNotNone(found)
                self.assertEqual(found[0], found[1])
                self.assertFalse(result['comparison_complete'])
                self.assertTrue(result['incomplete'][0]['path'].endswith(name))
                self.assertEqual(verdict, 'unknown')

    def test_bom_dotfile_metadata_partial_and_no_overlap(self):
        extra, copy = self.confirmed(), text(self.mine)
        for name, body in (('bom.txt', b'\xef\xbb\xbf' + copy.encode()), ('.ai.txt', copy), ('copy.txt~', copy),
                           ('meta.txt', '# 화면=1\n# 판정주체=AI\n\n' + copy)):
            with self.subTest(name=name):
                self.assertEqual(self.judged(name, body, extra)[:2], ('ai_identical', (64, 64)))
        for count in (1, 5):
            with self.subTest(partial=count):
                verdict, found, result = self.judged('p.txt', '# 화면=OTHER\n' + text(self.mine[:count]), extra)
                self.assertEqual((verdict, found, result['comparison_complete']), ('no_match_found', (count, count), True))
        verdict, found, result = self.judged('far.txt', 'z900=정상\n', extra)
        self.assertEqual((verdict, found), ('no_match_found', (0, 0)))
        verdict, found, result = self.judged('.DS_Store', b'\x00\x01\xff', extra)
        self.assertEqual((verdict, result['comparison_complete']), ('no_match_found', True))
        self.assertTrue(result['excluded_files'][0]['path'].endswith('.DS_Store'))
        self.assertEqual(self.judged('.junk.swp', b'\x00\x01\xff', extra)[0], 'unknown')
        self.assertEqual(self.judged('.DS_Store', copy, extra)[0], 'ai_identical')

    def test_identical_survives_neighbour_and_screen_relation_is_recorded(self):
        self.ai('final.txt', self.mine)
        (self.root / 'ai-responses/broken.txt').write_bytes(b'\xff\xfe\x00')
        result = self.run_gate()[1]
        self.assertEqual((result['verdict'], result['comparison_complete'], result['statement_confirmed']), ('ai_identical', False, False))
        (self.root / 'ai-responses/broken.txt').unlink()
        (self.root / 'ai-responses/final.txt').unlink()
        for name, head in (('s.txt', '# 화면=1\n'), ('o.txt', '# 화면=9\n'), ('u.txt', '')):
            (self.root / 'ai-responses' / name).write_text(head + text(self.mine), encoding='utf-8')
        found = {r['path'].rsplit('/', 1)[1]: r['screen'] for r in self.run_gate()[1]['comparisons']}
        self.assertEqual(found, {'s.txt': 'same', 'o.txt': 'other', 'u.txt': 'unknown'})

    def test_malformed_human_answers_are_refused(self):
        copy = text(self.mine)
        two = copy.replace('\nz2=', ' z2=', 1)
        for body in (two, copy.replace('\nz2=', ',z2=', 1), copy.replace('\nz2=', '; z2:', 1), copy.replace('\nz2=', '　ｚ２＝', 1),
                     copy.replace('z1=', 'z１='), 'a/back=확인;box:0,0,1,1;upper_left\n', 'a/back=확인;box:0,0,1,1;upper_left:\n',
                     'a/back=확인;box:0,0,1,1;upper_left:정상 upper_right:결함\n', 'a/back=확인;box:0,0,1,1;upper_left:정상;\n',
                     '- a/back=확인;box:0,0,1,1;upper_left:정상\n'):
            with self.subTest(body=body[:40]):
                self.answer.write_text(body, encoding='utf-8')
                self.assertEqual(self.run_gate(), (2, None))
        with self.assertRaises(ValueError):
            rater_gate.values(two)

    def test_bom_answer_and_normal_values_are_accepted(self):
        self.ai('final.txt', self.mine)
        self.answer.write_bytes(b'\xef\xbb\xbf# \xed\x99\x94\xeb\xa9\xb4=1\n' + text(self.mine).encode())
        self.assertEqual(self.run_gate()[1]['verdict'], 'ai_identical')
        line = 'z1=불가|2|사유=기타(흰 배경·박스선 겹침)\n# z2=a z3=b\n'
        self.assertEqual(rater_gate.values(line), {'z1': '불가|2|사유=기타(흰 배경·박스선 겹침)'})


if __name__ == '__main__':
    unittest.main()
