import contextlib
import io
import json
import os
import random
import tempfile
import unittest
from pathlib import Path

from tools import rater_gate

DATA = Path(os.environ.get('CARD_CONDITION_DATA_ROOT', Path(__file__).resolve().parents[1]))
RETEST = DATA / 'artifacts/cohort2-retest-20261125'
CHECK = DATA / 'artifacts/cohort2-label-check-20261124'
VALUES = ['정상|2'] * 3 + ['미세|1', '미세|2', '뚜렷|3', '불가|1|사유=반사']


def text(values):
    return ''.join(f'z{n}={v}\n' for n, v in enumerate(values, 1))


class RaterGateTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'responses').mkdir()
        (self.root / 'ai-responses').mkdir()
        self.answer = self.root / 'responses/a.txt'
        rng = random.Random(1)
        self.mine = [rng.choice(VALUES) for _ in range(64)]
        self.answer.write_text('# 화면=1\n' + text(self.mine), encoding='utf-8')

    def run_gate(self, *extra, answer=None):
        out = self.root / f'out{len(list(self.root.glob("out*")))}.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = rater_gate.main([str(answer or self.answer), '--out', str(out), *extra])
        return (code, json.loads(out.read_text()) if out.exists() else None)

    def ai(self, name, values):
        (self.root / 'ai-responses' / name).write_text(text(values), encoding='utf-8')

    def test_every_ai_file_is_recorded_and_identical_wins(self):
        self.ai('pass1.txt', ['x'] * 8 + self.mine[8:])
        self.ai('final.txt', self.mine)
        (self.root / 'ai-responses/note.log').write_text('no answers')
        _, result = self.run_gate()
        self.assertEqual(result['verdict'], 'ai_identical')
        self.assertEqual([(r['matches'], r['total']) for r in result['comparisons']], [(64, 64), (56, 64)])
        self.assertEqual(len(result['unreadable_ai_files']), 1)

    def test_seeded_random_answer_needs_the_sentence_for_no_match(self):
        rng = random.Random(2)
        self.ai('random.txt', [rng.choice(VALUES) for _ in range(64)])
        self.assertEqual(self.run_gate()[1]['verdict'], 'unknown')
        (self.root / 'expected.txt').write_text('내가 직접 판정\n', encoding='utf-8')
        (self.root / 'said.txt').write_text('내가 직접 판정', encoding='utf-8')
        extra = ['--statement', str(self.root / 'said.txt'), '--expected', str(self.root / 'expected.txt')]
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'no_match_found')
        (self.root / 'said.txt').write_text('직접 했음', encoding='utf-8')
        self.assertEqual(self.run_gate(*extra)[1]['verdict'], 'unknown')

    def test_partial_file_never_decides_and_nothing_compared_is_unknown(self):
        self.assertEqual(self.run_gate()[1]['verdict'], 'unknown')
        self.ai('one-zone.txt', self.mine[:1])
        _, result = self.run_gate()
        self.assertEqual((result['verdict'], result['comparisons'][0]['full_coverage']), ('unknown', False))

    def test_phone_format_and_refusals(self):
        line = 'a/back=확인;box:0,0,1,1;upper_left:결함;upper_right:정상'
        self.assertEqual(rater_gate.values(line), {'a/back/upper_left': '결함', 'a/back/upper_right': '정상'})
        with self.assertRaises(ValueError):
            rater_gate.values('z1=정상\nz1=결함')
        out = self.root / 'kept.json'
        out.write_text('old')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rater_gate.main([str(self.answer), '--out', str(out)]), 2)
            self.assertEqual(rater_gate.main([str(self.answer), '--ai', str(self.root / 'nope')]), 2)
        self.assertEqual(out.read_text(), 'old')

    def real(self, answer, expected_verdict, expected):
        _, result = self.run_gate(answer=answer)
        found = {Path(r['path']).name: (r['matches'], r['total']) for r in result['comparisons'] if r['full_coverage']}
        self.assertEqual(result['verdict'], expected_verdict)
        self.assertEqual({k: found[k] for k in expected}, expected)
        return result

    @unittest.skipUnless(RETEST.is_dir(), '미검증: 실자료 없음')
    def test_real_retest_answers_are_ai_identical(self):
        for screen, pass1 in (('A2', 56), ('B2', 50)):
            self.real(RETEST / f'responses/{screen}.txt', 'ai_identical',
                      {f'screen-{screen}-AI-pass1-20261125.txt': (pass1, 64), f'screen-{screen}-AI-final-20261125.txt': (64, 64)})

    @unittest.skipUnless(CHECK.is_dir(), '미검증: 실자료 없음')
    def test_real_screen1_is_ai_suspect(self):
        result = self.real(CHECK / 'responses/input-1.txt', 'ai_suspect', {'screen-1-AI-v3-final-20261124.txt': (62, 64)})
        self.assertLess(result['chance']['wilson95_upper'], 62 / 64)
        print('chance', result['chance'])


if __name__ == '__main__':
    unittest.main()
