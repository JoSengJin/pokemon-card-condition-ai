"""B5-3: budget.charge 호출 깊이 펼침(동작 불변)과 '같은 논리 실험 키는 한 번만 차감'(2026-11-28 사용자 결정 3: 실행 시작 시 차감,
인프라 장애 복구·한도 뒤 재개·체크포인트 재개에는 중복 차감 금지, 프로세스 중단·재시작으로 한도 우회 불가).

호출 연결(runner.drain·claude_job.execute에서 charge를 부르는 것)은 runner/claude_job을 고쳐야 해서 통합 뒤 일이다. 여기서는 깊이와 장부 멱등만 고정한다.
"""
import calendar
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from harness import budget, opstate
from tests import harness_depth_kit as kit
from tests.test_harness_supervisor_kit import events

WED = calendar.timegm((2030, 1, 9, 1, 0, 0))
KILL_CHILD = r'''
import os, signal, sys
sys.path.insert(0, sys.argv[1])
from harness import budget
def die(*a, **k):  # 장부에 차감 한 줄을 쓴 뒤·꼬리 기록 전에 실제 SIGKILL
    os.kill(os.getpid(), signal.SIGKILL)
budget.write_json = die
budget.charge(sys.argv[2], "experiment", 1, float(sys.argv[3]), key=sys.argv[4])
'''


class ChargeDepthTest(unittest.TestCase):
    def test_charge_depth_fits_drain_and_execute_call_sites(self):
        graph = kit.call_graph()
        depth, path = kit.longest("budget.charge", graph)
        # 호출 지점: runner.main -> drain -> charge, supervisor.run -> claude_job.execute -> charge (둘 다 charge까지 2회 전이)
        self.assertLessEqual(depth + 2, 4, path)
        self.assertLessEqual(kit.longest("budget.usage", graph)[0], 2)

    def test_exceeded_transition_is_identical_to_opstate_set_condition(self):
        """펼친 BUDGET_EXCEEDED 기록이 opstate.set_condition과 같은 상태 파일·장부 줄을 남긴다(이미 있던 한도 조건 보존 포함)."""
        roots = [tempfile.mkdtemp(), tempfile.mkdtemp()]
        for root in roots:
            opstate.set_condition(root, opstate.RATE_LIMITED_SHORT, WED - 5, "supervisor", "한도", {"next_try_at": WED + 60})
            for i in range(20):
                self.assertTrue(budget.charge(root, "experiment", 1, WED + i)["ok"])
        over = budget.charge(roots[0], "experiment", 1, WED + 30)
        info = {"kind": "experiment", "period": over["period"], "limit": 20, "requested": 1, "used": 20}
        opstate.set_condition(roots[1], opstate.BUDGET_EXCEEDED, WED + 30, "harness", "개발 예산 초과: experiment", info)
        opstate.notify(roots[1], WED + 30, "budget_exceeded", "개발 예산 초과(재승인 필요): experiment %s" % over["period"], info)
        self.assertEqual((over["ok"], over["reason"]), (False, "limit"))
        for name in (opstate.OPSTATE, "ledger.jsonl", opstate.NOTIFICATIONS):
            with open(os.path.join(roots[0], name), encoding="utf-8") as a, open(os.path.join(roots[1], name), encoding="utf-8") as b:
                self.assertEqual(a.read(), b.read(), name)
        with open(os.path.join(roots[0], opstate.OPSTATE), "w", encoding="utf-8") as handle:
            handle.write("{broken")  # 깨진 상태 파일: 덮어쓰지 않고 정지로 거절(set_condition과 같은 fail-closed)
        self.assertEqual(budget.charge(roots[0], "experiment", 1, WED + 40)["reason"], "halted:INTEGRITY_HALT")
        root = tempfile.mkdtemp()  # 정지 확인 뒤·전이 잠금 안에서 상태 파일이 깨진 경우(경합)와 실행자 없음: set_condition처럼 쓰지 않고 거절
        for i in range(20):
            budget.charge(root, "experiment", 1, WED + i, actor="")
        with self.assertRaises(opstate.OpStateError):
            budget.charge(root, "experiment", 1, WED + 50, actor="")
        broken = {"conditions": {opstate.INTEGRITY_HALT: {"reason": "x"}}, "unreadable": True}
        with mock.patch.object(opstate, "load", side_effect=[{"conditions": {}}, broken]), self.assertRaises(opstate.OpStateError):
            budget.charge(root, "experiment", 1, WED + 51)
        self.assertFalse(os.path.exists(os.path.join(root, opstate.OPSTATE)))

    def test_same_logical_key_is_charged_once_across_resume_and_limit(self):
        root = tempfile.mkdtemp()
        for i in range(20):
            self.assertTrue(budget.charge(root, "experiment", 1, WED + i, key="exp-%d" % i)["ok"])
        again = budget.charge(root, "experiment", 1, WED + 99, key="exp-5")  # 한도 뒤 재개·체크포인트 재개: 같은 논리 실험
        self.assertEqual((again["ok"], again.get("already"), again["used"]), (True, True, 20))
        self.assertNotIn(opstate.BUDGET_EXCEEDED, opstate.load(root)["conditions"])  # 이미 차감한 실험의 재개는 초과가 아니다
        new = budget.charge(root, "experiment", 1, WED + 100, key="exp-20")
        self.assertEqual((new["ok"], new["reason"]), (False, "limit"))
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 20)
        halted = budget.charge(root, "experiment", 1, WED + 101, key="exp-5")  # 정지 중에는 이미 차감한 키도 시작을 허락하지 않는다
        self.assertEqual((halted["ok"], halted["reason"]), (False, "halted:BUDGET_EXCEEDED"))

    def test_sigkill_between_ledger_and_tail_does_not_double_charge_or_reset(self):
        root = tempfile.mkdtemp()
        repo = kit.REPO
        for i in range(19):
            budget.charge(root, "experiment", 1, WED + i, key="exp-%d" % i)
        child = subprocess.run([sys.executable, "-c", KILL_CHILD, repo, root, str(WED + 50), "exp-19"], timeout=60)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        with open(os.path.join(root, budget.TAIL), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["seq"], 18)  # 꼬리는 kill 전 값 그대로
        self.assertEqual(budget.usage(root, "experiment", budget.period_of("experiment", WED)), 20)  # 장부 한 줄은 차감으로 인정
        retry = budget.charge(root, "experiment", 1, WED + 60, key="exp-19")  # 재시작 뒤 같은 실험: 다시 차감하지 않는다
        self.assertEqual((retry["ok"], retry.get("already"), retry["used"]), (True, True, 20))
        path = os.path.join(root, budget.BUDGET)
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")[:-1]
        with open(path, "w", encoding="utf-8") as handle:  # 마지막 줄들을 잘라 사용량을 되돌리려는 시도: charge도 거절
            handle.write("\n".join(lines[:-2]) + "\n")
        with self.assertRaises(budget.BudgetError):
            budget.charge(root, "vision_zone", 1, WED + 62)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        self.assertFalse(budget.charge(root, "experiment", 1, WED + 61, key="exp-20")["ok"])  # 재시작으로 한도가 풀리지 않는다
        os.remove(os.path.join(root, budget.TAIL))  # 꼬리 파일만 지워 사용량을 되돌리려는 시도
        with self.assertRaises(budget.BudgetError):
            budget.usage(root, "experiment", budget.period_of("experiment", WED))


if __name__ == "__main__":
    unittest.main()
