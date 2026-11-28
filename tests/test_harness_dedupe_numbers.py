"""4차 결함 I1·I2·I3(사용자 결정 2026-11-28 숫자 표기): 숫자는 자료형을 아는 곳에서만 값으로 본다.

- 명령(command) 토큰은 자료형을 알 수 없어 숫자로 바꾸지 않는다(문자 그대로 비교). 그래서 1e3과 1000, +5와 5, .5와 0.5, 0.10과 0.1은 다른
  조건으로 등록된다. 이전 3차 기대(부호·소수·지수 표기 7쌍 = 같은 값 = 중복)는 바뀌었다. 근거: 사용자 결정 2026-11-28 숫자 표기
  "자료형을 확인할 수 없는 경우 임의로 숫자로 변환하지 않는다"(3차에 넣은 십진 정규화가 1e3 ≠ 1000 회귀(I1)와 거대 지수 예외(I2)를 만들었다).
  한계: 같은 실험이 숫자 표기만 바꿔 다시 등록될 수 있다(수치 파라미터는 config로 넘기면 자료형이 있어 중복으로 판정된다).
- config(JSON, 자료형이 있음)의 수치는 자료형과 값으로 본다: int·float·bool은 서로 다른 자료형(1 ≠ 1.0, true ≠ 1, false ≠ 0, [1] ≠ [1.0]),
  같은 자료형 안에서는 값으로 비교(-0.0 = 0.0, 큰 정수는 정확히). 문자열은 원래 값 그대로("0.10" ≠ "0.1", "1" ≠ 1). NaN·무한대(JSON 글자
  1e400 포함)·MAX_INT_DIGITS자리를 넘는 정수·JSON이 아닌 값·너무 깊은 중첩은 등록 거절(ContractError). seed는 정수 필드 그대로.
- 거대한 숫자 토큰·config 수치·깊게 중첩된 선언은 등록 경로 밖으로 ContractError 아닌 예외를 내지 않는다(I2): 선언 하나는 그 선언만 거절·알림하고
  Supervisor는 INTEGRITY_HALT로 멈추지 않는다(다른 선언은 등록된다).
"""
import json
import os
import shutil
import tempfile
import unittest

from harness import contract as ct
from harness import dedupe, graph, opstate, queue, supervisor
from tests.test_harness_dedupe_keys import exp
from tests.test_harness_git_kit import git_source
from tests.test_harness_support import make_contract
from tests.test_harness_supervisor_kit import events

T0 = 1_800_000_000.0
BIG = "1e1000000000000000000"  # 4차 I2: 3차 코드에서 decimal.InvalidOperation(ContractError 아님)으로 Supervisor 전체 정지
COMMAND_PAIRS = [("1e3", "1000"), ("2e1", "20"), ("1e2", "100"), ("1.5e2", "150"), ("2.5e1", "25"),  # I1 쌍(3차: 일부만 중복)
                 ("5", "+5"), ("0", "-0"), ("0.5", ".5"), ("0.001", "1e-3"), ("1e-3", "1E-3"), ("2.5e3", "2.5E+3"),  # 3차 기대: 중복
                 ("123456789012345678901234567890", "+123456789012345678901234567890"),  # 3차 기대: 중복
                 ("12345678901234567", "12345678901234568"), ("1.10", "1.1"), ("01", "1"), ("0.10", "0.1"), ("1.0", "1"),
                 ("1.", "1"), ("007", "7"), (BIG, "1e1000000000000000001"), ("9" * 5000, "9" * 4999 + "8")]
CONFIG_SAME = [(-0.0, 0.0), (0.1, 1e-1), (2 ** 70, 2 ** 70), ([1.5, {"a": True}], [1.5, {"a": True}]), ("0.10", "0.10")]
CONFIG_DIFFERENT = [(1, 1.0), (True, 1), (False, 0), ([1], [1.0]), ("1", 1), ("0.10", "0.1"), (2 ** 70, 2 ** 70 + 1),
                    (0.1, 0.1000000000000001)]


def _with(src, token):
    return exp(src, command=["python", "train.py", "--x", token, "--train", "{input:data/train.csv}", "--val", "{input:data/val.csv}"])


def _conf(src, value):
    return exp(src, config={"x": value})


class DedupeNumberTest(unittest.TestCase):
    def _pair(self, make, first, second):
        """새 root·원본 폴더에 make(src, first) 실험을 등록하고, risk만 다른(task_key가 다른) make(src, second)의 등록 결과를 돌려준다
        ((첫 키, 둘째 키 또는 DuplicateTask))."""
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)
        key = queue.enqueue(root, make(src, first), T0, source_root=src)
        try:
            return key, queue.enqueue(root, dict(make(src, second), risk="high"), T0 + 1, source_root=src)
        except queue.DuplicateTask as exc:
            return key, exc

    def test_command_number_tokens_are_compared_as_written(self):
        for first, second in COMMAND_PAIRS:
            key, other = self._pair(_with, first, second)
            self.assertIsInstance(other, str, (first[:20], second[:20]))  # 사용자 결정 2026-11-28 숫자 표기(이전 기대 일부: 중복)
            self.assertNotEqual(key, other, (first[:20], second[:20]))
        for token in ("1e3", "0.10", BIG):  # 글자까지 같은 토큰은 그대로 중복이다(risk만 다름)
            key, other = self._pair(_with, token, token)
            self.assertIsInstance(other, queue.DuplicateTask, token[:20])
            self.assertEqual(other.existing, key)

    def test_config_numbers_compare_by_type_and_then_by_value(self):
        for first, second in CONFIG_SAME:
            key, other = self._pair(_conf, first, second)
            self.assertIsInstance(other, queue.DuplicateTask, (first, second))
            self.assertEqual(other.existing, key, (first, second))
        for first, second in CONFIG_DIFFERENT:  # 이전 2·3차 기대: config 1 = 1.0 중복(사용자 결정 2026-11-28 숫자 표기로 바뀜)
            key, other = self._pair(_conf, first, second)
            self.assertIsInstance(other, str, (first, second))
            self.assertNotEqual(key, other, (first, second))

    def test_non_finite_huge_deep_or_non_json_config_values_are_contract_errors(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)
        huge, deep = 10 ** (dedupe.MAX_INT_DIGITS + 1), []
        for _ in range(50000):
            deep = [deep]
        bad = [_conf(src, float("nan")), _conf(src, float("inf")), _conf(src, -float("inf")), _conf(src, huge), _conf(src, {1, 2}),
               _conf(src, deep), exp(src, seed=huge)]
        for index, task in enumerate(bad):
            with self.assertRaises(ct.ContractError, msg=index):
                queue.enqueue(root, task, T0, source_root=src)
        self.assertFalse(os.path.isdir(os.path.join(root, "tasks")))
        self.assertIsInstance(dedupe.json_number("9" * (dedupe.MAX_INT_DIGITS + 1)), float)  # 파일 읽기가 정수 변환 상한으로 깨지지 않는다
        self.assertEqual((dedupe.json_number("-0.0"), dedupe.json_number("12")), (0.0, 12))

    def test_huge_numbers_reject_only_their_declaration_and_do_not_halt_the_supervisor(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)
        token = _with(src, BIG)
        self.assertEqual(len(graph.register_missing(tempfile.mkdtemp(), {ct.task_key(token): token}, T0, source_root=src)["registered"]), 1)
        good = make_contract("good", task_type="deterministic")
        text = json.dumps({ct.task_key(token): token, ct.task_key(good): good})[:-1]
        for bad_key, literal in (("a" * 64, "1e1000000000000000000"), ("b" * 64, "9" * (dedupe.MAX_INT_DIGITS + 1))):
            text += ', "%s": %s' % (bad_key, json.dumps(_conf(src, 0)).replace('"x": 0', '"x": ' + literal))
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        with open(os.path.join(root, supervisor.DECLARED), "w", encoding="utf-8") as handle:
            handle.write(text + "}")
        out = supervisor.run(root, max_cycles=2, poll_s=0, sleep_fn=lambda s: None, source_root=src)
        self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT)
        for key in (ct.task_key(token), ct.task_key(good)):
            self.assertTrue(os.path.isfile(os.path.join(root, "tasks", key, "contract.json")), key)
        rejected = sorted(e["data"]["declaration"] for e in events(root, "declaration_rejected"))
        self.assertEqual(rejected, ["a" * 64, "b" * 64])  # 그 선언만 한 번씩(회차마다 다시 알리지 않는다)
        deep = tempfile.mkdtemp()
        os.makedirs(os.path.join(deep, "supervisor"))
        with open(os.path.join(deep, supervisor.DECLARED), "w", encoding="utf-8") as handle:
            handle.write('{"%s": %s}' % ("c" * 64, "[" * 100000 + "]" * 100000))  # 파일 단위 문제: 그 회차 등록만 건너뜀(정지 아님)
        self.assertNotEqual(supervisor.run(deep, max_cycles=1, poll_s=0, sleep_fn=lambda s: None)["state"], opstate.INTEGRITY_HALT)


if __name__ == "__main__":
    unittest.main()
