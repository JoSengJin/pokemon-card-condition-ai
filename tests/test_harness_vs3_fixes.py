"""VS3 독립 검증 필수 결함 D1~D4 수정 시험(artifacts/harness-resume-20261127/verify-vs3-20261128.md).

- D1: Claude가 쓴 next_plan.json 내용으로 생기는 예외는 그 계획만 거절·대기한다(Supervisor 전체 INTEGRITY_HALT 없음).
- D2: 승인 변수 experiment_parameter.value는 수로 비교한다(1 = 1.0): baseline·대조 값과 같으면 거절, 기각 대조는 int·float 두 표기로.
  전역 dedupe의 config 자료형 규칙(사람 등록 config의 1 ≠ 1.0)은 바꾸지 않는다.
가짜 실험 executor·합성 git 원본만 쓴다(실제 ./experiment·claude·모델 호출 없음). 합성 통과는 모델 성능 근거가 아니다.
"""
import functools
import json
import os
import unittest
from unittest import mock

from harness import graph, opstate, plan_gate, queue, supervisor
from harness.jsonio import read_json
from tests import harness_plan_gate_kit as kit
from tests import test_harness_vs3_gate as vs3_gate  # 모듈로 가져온다(시험 클래스를 이 모듈에 다시 노출하지 않게)


class PlanGateFixTest(unittest.TestCase):
    _chain = vs3_gate.PlanGateTest._chain  # 대조 VERIFIED → 분석 완료(사양대로 쓴 next_plan.json) → gate (같은 도구를 다시 쓴다)
    _refused = vs3_gate.PlanGateTest._refused

    def test_d1_plan_content_exceptions_hold_only_that_plan(self):
        huge = json.dumps(kit.proposal(kit.control("0" * 40))).replace("0.7", "1" + "0" * 400)  # 401자리 정수: int로 읽히고 float 범위 밖
        got = self._chain({"raw": huge})
        self.assertTrue(got["reason"].startswith("refused") and "유한한 숫자" in got["reason"], got["reason"])
        root, src, head = got["root"], got["src"], got["head"]
        other = self._chain(world=(root, src, head), plan={"hid": "H2", "value": 0.65})  # 같은 root의 독립 계획
        self.assertIsNone(other["reason"])
        out = supervisor.run(root, max_cycles=2, poll_s=0, sleep_fn=float, now_fn=functools.partial(float, kit.NOW), source_root=src)
        self.assertEqual((out["state"], opstate.effective(opstate.load(root))), (opstate.RUNNING, opstate.RUNNING))
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        self.assertEqual([k for k, c in tasks.items() if c["depends_on"] == [got["analyze"]]], [])
        self.assertEqual(len([k for k, c in tasks.items() if c["depends_on"] == [other["analyze"]]]), 1)  # 독립 계획은 등록된다
        self.assertIn("plan:" + got["analyze"], read_json(os.path.join(root, graph.REJECTED)))
        for exc in (IndexError("x"), ZeroDivisionError("x"), OverflowError("x")):  # 재현 지점 밖의 같은 원인: 계획 검사의 다른 예외 부류
            with mock.patch.object(plan_gate, "_diff", side_effect=exc):
                got = self._chain()
            self.assertTrue(got["reason"].startswith("waiting: " + type(exc).__name__), got["reason"])

    def test_d2_type_only_change_of_the_approved_variable_is_the_same_number(self):
        for words, chain in (("baseline 또는 대조", {"spec": {"over": {"value": 1}}, "plan": {"value": 1.0}}),  # A: 대조 1.0 → 1(실질 변경 0)
                             ("baseline 또는 대조", {"spec": {"over": {"value": 0.5}}}),  # C: value = baseline(기존 check_experiment_parameter 규칙)
                             ("기각·중복 가설", {"spec": {"over": {"value": 2}}, "fail": 2.0}),  # B: 실패 F 2.0 → 2
                             ("기각·중복 가설", {"spec": {"over": {"value": 2.0}}, "fail": 2})):  # B′: 사람이 int로 등록한 실패 F 2 → 2.0
            self._refused(words, **chain)
        got = self._chain({"over": {"value": 2.5}}, fail=2.0)  # 다른 수는 그대로 통과(과잉 차단 없음)
        self.assertIsNone(got["reason"])
        dup = queue.enqueue(got["root"], kit.control(got["head"], value=2, hid="Z"), kit.NOW, source_root=got["src"])  # 전역 규칙은 그대로: 사람 등록 config의 2 ≠ 2.0
        self.assertTrue(os.path.isdir(os.path.join(got["root"], "tasks", dup)))


if __name__ == "__main__":
    unittest.main()
