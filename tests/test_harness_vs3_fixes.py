"""VS3 독립 검증 필수 결함 D1~D4 수정 시험(artifacts/harness-resume-20261127/verify-vs3-20261128.md).

- D1: Claude가 쓴 next_plan.json 내용으로 생기는 예외는 그 계획만 거절·대기한다(Supervisor 전체 INTEGRITY_HALT 없음).
가짜 실험 executor·합성 git 원본만 쓴다(실제 ./experiment·claude·모델 호출 없음). 합성 통과는 모델 성능 근거가 아니다.
"""
import functools
import json
import os
import unittest
from unittest import mock

from harness import graph, opstate, plan_gate, supervisor
from harness.jsonio import read_json
from tests import harness_plan_gate_kit as kit
from tests import test_harness_vs3_gate as vs3_gate  # 모듈로 가져온다(시험 클래스를 이 모듈에 다시 노출하지 않게)


class PlanGateFixTest(unittest.TestCase):
    _chain = vs3_gate.PlanGateTest._chain  # 대조 VERIFIED → 분석 완료(사양대로 쓴 next_plan.json) → gate (같은 도구를 다시 쓴다)

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


if __name__ == "__main__":
    unittest.main()
