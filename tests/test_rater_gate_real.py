import contextlib
import io
import unittest
from pathlib import Path

from tests.test_rater_gate import CHECK, RETEST, RaterGateBase
from tools import rater_gate

class RaterGateTestMore(RaterGateBase):
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
