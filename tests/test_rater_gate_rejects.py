"""Review 2026-11-27 I-4, I-5: broken answer lines and AI files that were never really compared."""
import json
import random
import unittest

from tests.test_rater_gate import VALUES, RaterGateBase, text


class RaterGateRejectTest(RaterGateBase):
    def confirmed(self):
        (self.root / 'said.txt').write_text('직접 판정', encoding='utf-8')
        rng = random.Random(2)
        self.ai('unrelated.txt', [rng.choice(VALUES) for _ in range(64)])
        return ['--statement', str(self.root / 'said.txt'), '--expected', str(self.root / 'said.txt')]

    def test_broken_answer_line_is_refused(self):
        self.ai('final.txt', self.mine)
        for old, new in (('z1=', 'z1 :'), ('z2=', 'Z2='), ('z64=' + self.mine[63], 'z64='), ('z3=' + self.mine[2], f'z3={self.mine[2]} # 근거')):
            with self.subTest(new=new):
                self.answer.write_text(text(self.mine).replace(old, new), encoding='utf-8')
                self.assertEqual(self.run_gate(), (2, None))

    def test_uncompared_ai_output_blocks_no_match(self):
        extra = self.confirmed()
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'no_match_found')
        for name, body in (('conflict.txt', text(self.mine) + 'z1=정정\n'), ('judgments.json', json.dumps(self.mine)),
                           ('commented.txt', text(self.mine).replace('\n', ' # 근거\n')),
                           ('typo.txt', text(self.mine).replace('z1=', 'z1 :'))):
            with self.subTest(name=name):
                (self.root / 'ai-responses' / name).write_text(body, encoding='utf-8')
                self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'unknown')
                (self.root / 'ai-responses' / name).unlink()
        (self.root / 'ai-responses/run.log').write_text('작업 기록')
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'no_match_found')

    def test_other_screen_cannot_prove_no_match_but_can_still_flag(self):
        extra = self.confirmed()
        (self.root / 'ai-responses/unrelated.txt').rename(self.root / 'other.txt')
        other = '# 화면=OTHER\n' + (self.root / 'other.txt').read_text(encoding='utf-8')
        (self.root / 'ai-responses/other.txt').write_text(other, encoding='utf-8')
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'unknown')
        (self.root / 'ai-responses/copy.txt').write_text('# 화면=OTHER\n' + text(self.mine), encoding='utf-8')
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'ai_identical')


if __name__ == '__main__':
    unittest.main()
