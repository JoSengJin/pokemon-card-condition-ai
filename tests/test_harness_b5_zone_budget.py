"""B5-5: 논리 구역 수 × 기존 주간 예산 장부(budget.charge, key=task_key). budget.py는 고치지 않고 기존 잠금·멱등을 시험으로 고정한다.

claude_job 연결 전이라 장부 수준 시험이다(실제 claude·비전 호출 없음). 한도 300은 논리 구역 수이며 실제 AI 사용량 한도가 아니다.
"""
import calendar
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import budget, contract as ct, logical_zones, opstate
from tests import harness_depth_kit as kit
from tests.test_harness_b5_logical_zones import ITEM, staged
from tests.test_harness_supervisor_kit import events
from tests.test_harness_support import make_contract

WED = calendar.timegm((2030, 1, 9, 1, 0, 0))
WEEK = "week:2030-W02"
# argv: root amount key point. point: race(go 파일을 기다린 뒤 차감) | before(장부 append 직전 kill) | after_row(append 직후·꼬리 전) |
# after_tail(꼬리까지 쓰고 반환 전)
CHILD = r'''
import json, os, signal, sys, time
from harness import budget, ledger
root, amount, key, point = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
def die():
    os.kill(os.getpid(), signal.SIGKILL)
real_append, real_write = ledger.append, budget.write_json
if point == "before":
    ledger.append = lambda *a: die()
elif point == "after_row":
    budget.write_json = lambda *a: die()
elif point == "after_tail":
    budget.write_json = lambda *a: (real_write(*a), die())
elif point == "race":
    open(os.path.join(root, "ready-%d" % os.getpid()), "w").close()
    while not os.path.exists(os.path.join(root, "go")):
        time.sleep(0.005)
print(json.dumps(budget.charge(root, "vision_zone", amount, float(sys.argv[5]), key=key)))
'''


def spawn(root, amount, key, point):
    return subprocess.Popen([sys.executable, "-c", CHILD, root, str(amount), key, point, str(WED)], cwd=kit.REPO,
                            env=dict(os.environ, PYTHONPATH=kit.REPO, PYTHONDONTWRITEBYTECODE="1"), stdout=subprocess.PIPE)


def race(case, root, jobs):
    """jobs [(amount, key)]를 프로세스마다 하나씩, 모두 준비된 뒤 동시에 차감한다. 결과 dict 목록."""
    children = [spawn(root, amount, key, "race") for amount, key in jobs]
    for child in children:
        case.addCleanup(child.kill)
    deadline = time.monotonic() + 60
    while len([n for n in os.listdir(root) if n.startswith("ready-")]) < len(jobs):
        case.assertLess(time.monotonic(), deadline)
        time.sleep(0.01)
    open(os.path.join(root, "go"), "w").close()
    return [json.loads(child.communicate(timeout=60)[0]) for child in children]


class ZoneBudgetTest(unittest.TestCase):
    def test_changed_list_is_a_new_task_charged_again_but_resuming_the_same_task_is_not(self):
        root, tasks = tempfile.mkdtemp(), []
        for zones in (["a", "b"], ["a", "c"]):  # 같은 수·다른 목록
            text = json.dumps({"selected": [dict(ITEM, region_id=z, zone=z) for z in zones]})
            task_dir, staged_contract = staged(text)
            task = make_contract("v", inputs=staged_contract["inputs"], task_type="silver_labeling", needs_llm=True)
            tasks.append((task_dir, task, ct.task_key(task)))
        self.assertNotEqual(tasks[0][2], tasks[1][2])
        for task_dir, task, key in tasks + tasks:  # 두 번째 바퀴 = 같은 불변 입력의 재개·복구
            self.assertTrue(budget.charge(root, "vision_zone", logical_zones.count_logical_zones(task_dir, task), WED, key=key)["ok"])
        self.assertEqual((budget.usage(root, "vision_zone", WEEK), len(events(root, "charge", budget.BUDGET))), (4, 2))
        later = budget.charge(root, "vision_zone", 2, WED + 7 * 86400, key=tasks[0][2])  # 다음 주의 재개도 다시 차감하지 않는다
        self.assertEqual((later["ok"], later.get("already"), later["used"]), (True, True, 0))

    def test_parallel_charges_never_exceed_the_weekly_limit(self):
        for _ in range(3):
            root = tempfile.mkdtemp()
            results = race(self, root, [(100, "task-%d" % i) for i in range(8)])
            self.assertEqual(sum(r["ok"] for r in results), 3, results)
            self.assertEqual({r["reason"] for r in results if not r["ok"]} - {"limit", "halted:BUDGET_EXCEEDED"}, set())
            self.assertEqual(budget.usage(root, "vision_zone", WEEK), 300)
            self.assertIn(opstate.BUDGET_EXCEEDED, opstate.load(root)["conditions"])
        root = tempfile.mkdtemp()  # 같은 작업을 동시에 여럿이 차감해도 한 줄
        results = race(self, root, [(200, "same")] * 6)
        self.assertEqual((sum(r["ok"] for r in results), sum(not r.get("already") for r in results)), (6, 1), results)
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 1)

    def test_sigkill_around_the_charge_neither_loses_nor_doubles_it(self):
        for point, rows_after_kill in (("before", 1), ("after_row", 2), ("after_tail", 2)):
            with self.subTest(point):
                root = tempfile.mkdtemp()
                budget.charge(root, "vision_zone", 250, WED, key="earlier")
                child = spawn(root, 50, "job", point)
                child.communicate(timeout=60)
                self.assertEqual(child.returncode, -signal.SIGKILL)
                self.assertEqual(len(events(root, "charge", budget.BUDGET)), rows_after_kill)
                retry = budget.charge(root, "vision_zone", 50, WED + 1, key="job")  # 재시작: 빠졌으면 차감, 있으면 그대로
                self.assertEqual((retry["ok"], bool(retry.get("already")), retry["used"]), (True, point != "before", 300))
                self.assertEqual(budget.usage(root, "vision_zone", WEEK), 300)
                self.assertFalse(budget.charge(root, "vision_zone", 1, WED + 2, key="next")["ok"])

    def test_half_written_ledger_line_stops_charging_instead_of_guessing(self):
        root = tempfile.mkdtemp()
        budget.charge(root, "vision_zone", 10, WED, key="a")
        path = os.path.join(root, budget.BUDGET)
        with open(path, "r+", encoding="utf-8") as handle:
            line = handle.read()
            handle.write(line[:len(line) // 2])  # 두 번째 줄을 쓰다 죽은 모양
        for key in ("a", "b"):  # 이미 차감한 키의 재개도 사람이 장부를 확인하기 전에는 거절
            with self.assertRaises(budget.BudgetError):
                budget.charge(root, "vision_zone", 1, WED + 1, key=key)

    def test_a_single_list_over_the_weekly_limit_sets_the_existing_global_stop(self):
        """기존 정책 고정(바꾸지 않음): 한 작업의 301구역도 BUDGET_EXCEEDED(전체 개발 정지, 사람 재승인)를 켠다."""
        root = tempfile.mkdtemp()
        items = [dict(ITEM, region_id=str(i), image_sha=str(i)) for i in range(301)]
        count = logical_zones.count_logical_zones(*staged(json.dumps({"selected": items})))
        over = budget.charge(root, "vision_zone", count, WED, key="big")
        self.assertEqual((count, over["ok"], over["reason"], over["used"]), (301, False, "limit", 0))
        self.assertEqual(opstate.effective(opstate.load(root)), opstate.BUDGET_EXCEEDED)


if __name__ == "__main__":
    unittest.main()
