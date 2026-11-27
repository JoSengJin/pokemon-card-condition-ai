"""3차 결함 H2: 명령의 숫자 토큰은 실제로 다른 값을 같은 값으로 접지 않는다(승인 계약: 실행 조건이 하나라도 실제로 다르면 통과).

- 정수 모양 토큰(앞자리 0 없음)은 정확히 비교한다(float를 거치지 않는다: 1e15를 넘는 정수도 1 차이를 구분). 같다고 보는 것은 부호 표기
  (+5 = 5, -0 = 0)뿐이다.
- 앞자리 0이 있는 토큰(01, 007)과 소수점 끝 0·끝 점(1.10, 0.10, 1.0, 1.)은 문자열 그대로 둔다: 문자열 ID·버전일 수 있어 같은 값인지
  판별할 수 없다(이전 2차 기대 0.10 = 0.1, 1.0 = 1은 바뀌었다: 다르게 봐서 생기는 손해는 같은 실험의 중복 등록 가능성이고, 같다고 봐서
  생기는 손해는 실제로 다른 실험의 등록 거절인데 승인 계약은 후자를 금지한다).
- 그 밖의 소수·지수 토큰은 십진 값으로 정확히 비교한다(.5 = 0.5, 1e-3 = 0.001, 자릿수가 많아도 반올림하지 않는다).
"""
import shutil
import tempfile
import unittest

from harness import queue
from tests.test_harness_dedupe_keys import exp
from tests.test_harness_git_kit import git_source

T0 = 1_800_000_000.0
DIFFERENT = [("12345678901234567", "12345678901234568"), (str(2 ** 70), str(2 ** 70 + 1)), ("1.10", "1.1"), ("01", "1"),
             ("0.10", "0.1"), ("1.0", "1"), ("1.", "1"), ("007", "7"),
             ("1.2345678901234567890123456789012", "1.2345678901234567890123456789013")]
SAME = [("5", "+5"), ("0", "-0"), ("0.5", ".5"), ("0.001", "1e-3"), ("1e-3", "1E-3"), ("2.5e3", "2.5E+3"),
        ("123456789012345678901234567890", "+123456789012345678901234567890")]


def _with(src, token):
    return exp(src, command=["python", "train.py", "--x", token, "--train", "{input:data/train.csv}", "--val", "{input:data/val.csv}"])


class DedupeNumberTest(unittest.TestCase):
    def _pair(self, first, second):
        """새 root·원본 폴더에 first 토큰 실험을 등록하고 second 토큰 실험의 등록 결과를 돌려준다((첫 키, 둘째 키 또는 DuplicateTask))."""
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)
        key = queue.enqueue(root, _with(src, first), T0, source_root=src)
        try:
            return key, queue.enqueue(root, _with(src, second), T0 + 1, source_root=src)
        except queue.DuplicateTask as exc:
            return key, exc

    def test_numbers_that_really_differ_are_registered(self):
        for first, second in DIFFERENT:
            key, other = self._pair(first, second)
            self.assertIsInstance(other, str, (first, second))
            self.assertNotEqual(key, other, (first, second))

    def test_same_numbers_written_differently_are_duplicates(self):
        for first, second in SAME:
            key, other = self._pair(first, second)
            self.assertIsInstance(other, queue.DuplicateTask, (first, second))
            self.assertEqual(other.existing, key, (first, second))


if __name__ == "__main__":
    unittest.main()
