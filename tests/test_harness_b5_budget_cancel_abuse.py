"""B5-4: 실험 예산 차감 취소(사용자 결정 3, 2026-11-28). 실행되지 않았음이 객관적으로 확인된 경우(어댑터 not_started)에만 그 시도가 새로 한 차감을
취소한다. 여기서는 취소를 악용한 우회(위조·중복 취소 줄)와 차감·취소 직전·직후 실제 SIGKILL, 병렬 취소·차감, 반쯤 쓴 장부 줄을 본다.
합성 root만 쓴다(실제 실험·모델 호출 없음).
"""
import calendar
import functools
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import budget, ledger, opstate
from tests import harness_depth_kit as kit
from tests.test_harness_supervisor_kit import events

WED = calendar.timegm((2030, 1, 9, 1, 0, 0))  # 2030-W02
CHILD = r'''
import os, signal, sys, time
sys.path.insert(0, sys.argv[1])
from harness import budget
def die(*a, **k):
    os.kill(os.getpid(), signal.SIGKILL)
mode, root = sys.argv[2], sys.argv[3]
if mode == "cancel_before_append":
    budget.ledger.append = die
elif mode in ("cancel_after_append", "charge_after_append"):
    budget.write_json = die
if mode == "race":  # 같은 시각에 시작해 같은 차감 하나를 동시에 취소한다
    while time.time() < float(sys.argv[6]):
        time.sleep(0.001)
if mode.startswith("charge"):
    print(budget.charge(root, "experiment", 1, float(sys.argv[5]), key=sys.argv[4])["ok"])
else:
    print(budget.cancel(root, "experiment", sys.argv[4], int(sys.argv[5]), 1894000000.0)["ok"])
'''


def _child(*args):
    return subprocess.run([sys.executable, "-c", CHILD, kit.REPO] + [str(a) for a in args], capture_output=True, text=True, timeout=60)


def _week(root, now=WED):
    return budget.usage(root, "experiment", budget.period_of("experiment", now))


class BudgetCancelAbuseTest(unittest.TestCase):
    def test_forged_or_mismatched_cancel_rows_stop_every_charge(self):
        def forge(rows):
            root = tempfile.mkdtemp()
            budget.charge(root, "experiment", 1, WED, key="K0")
            for event, data in rows:  # budget.cancel을 거치지 않은 줄(꼬리도 맞춰 잘림으로 보이지 않게)
                entry = ledger.append(os.path.join(root, budget.BUDGET), WED + 10, event, data)
                with open(os.path.join(root, budget.TAIL), "w", encoding="utf-8") as handle:
                    json.dump({"hash": entry["hash"], "seq": entry["seq"]}, handle)
            return root
        good = {"kind": "experiment", "key": "K0", "charge_seq": 0, "period": "week:2030-W02", "amount": 1, "actor": "x", "reason": "not_started"}
        later = {"kind": "experiment", "period": "week:2030-W02", "amount": 1, "actor": "x", "key": "K2"}
        cases = {"no_charge": [("cancel", dict(good, charge_seq=9))], "amount": [("cancel", dict(good, amount=5))],
                 "period": [("cancel", dict(good, period="week:2030-W03"))], "key": [("cancel", dict(good, key="K1"))],
                 "kind": [("cancel", dict(good, kind="vision_zone"))], "seq_type": [("cancel", dict(good, charge_seq="0"))],
                 "points_at_itself": [("cancel", dict(good, charge_seq=1))], "before_charge": [("cancel", dict(good, key="K2", charge_seq=2)),
                                                                                            ("charge", later)],
                 "double": [("cancel", good), ("cancel", good)], "unknown_event": [("refund", {"kind": "experiment", "amount": -1})]}
        for name, rows in cases.items():
            with self.subTest(name=name):
                root = forge(rows)
                with self.assertRaises(budget.BudgetError):
                    budget.charge(root, "experiment", 1, WED + 20, key="new")
                with self.assertRaises(budget.BudgetError):
                    _week(root)
                with self.assertRaises(budget.BudgetError):
                    budget.cancel(root, "experiment", "K0", 0, WED + 21)
        self.assertEqual(_week(forge([("cancel", good)])), 0)  # 같은 모양의 한 줄은 정상(위 실패가 형식 때문이 아님)

    def test_sigkill_around_charge_and_cancel_neither_double_counts_nor_frees_budget(self):
        root = tempfile.mkdtemp()
        for i in range(19):
            budget.charge(root, "experiment", 1, WED + i, key="exp-%d" % i)
        self.assertEqual(_child("charge_after_append", root, "K", WED + 50).returncode, -signal.SIGKILL)  # 차감 직후 kill
        self.assertEqual(_week(root), 20)
        self.assertTrue(budget.charge(root, "experiment", 1, WED + 51, key="K").get("already"))  # 재시작: 다시 빼지 않는다
        path = os.path.join(root, budget.BUDGET)
        with open(path, encoding="utf-8") as handle:
            whole = handle.read()
        with open(path, "w", encoding="utf-8") as handle:  # 재시작 뒤 꼬리를 맞췄으므로 꼬리 없던 그 줄을 지우면 잘림으로 보인다
            handle.write("".join(line + "\n" for line in whole.split("\n")[:-2]))
        with self.assertRaises(budget.BudgetError):
            _week(root)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(whole)
        seq = events(root, "charge", budget.BUDGET)[-1]["seq"]
        self.assertEqual(_child("cancel_before_append", root, "K", seq).returncode, -signal.SIGKILL)  # 취소 직전 kill: 차감 유지
        self.assertEqual((_week(root), len(events(root, "cancel", budget.BUDGET))), (20, 0))
        self.assertEqual(_child("cancel_after_append", root, "K", seq).returncode, -signal.SIGKILL)  # 취소 직후(꼬리 전) kill
        self.assertEqual(_week(root), 19)
        again = budget.cancel(root, "experiment", "K", seq, WED + 60)  # 재시작 뒤 같은 취소: 한 번만
        self.assertEqual((again["ok"], again.get("already"), _week(root)), (True, True, 19))
        self.assertEqual(len(events(root, "cancel", budget.BUDGET)), 1)
        self.assertTrue(budget.charge(root, "experiment", 1, WED + 61, key="K2")["ok"])
        self.assertEqual(budget.charge(root, "experiment", 1, WED + 62, key="K3")["reason"], "limit")  # 재시작으로 한도가 풀리지 않는다
        root = tempfile.mkdtemp()
        budget.charge(root, "experiment", 1, WED, key="K")
        with open(os.path.join(root, budget.BUDGET), "a", encoding="utf-8") as handle:
            handle.write('{"seq": 1, "event": "cancel", "data": {"kind": "experi')  # 반쯤 쓴 취소 줄
        for call in (functools.partial(budget.charge, root, "experiment", 1, WED + 1, key="N"),
                     functools.partial(budget.cancel, root, "experiment", "K", 0, WED + 2), functools.partial(_week, root)):
            with self.assertRaises(budget.BudgetError):
                call()

    def test_parallel_cancels_of_one_charge_write_one_row_and_parallel_charges_stay_in_limit(self):
        root = tempfile.mkdtemp()
        seq = budget.charge(root, "experiment", 1, WED, key="K")["seq"]
        start = time.time() + 1.0  # race 모드는 실제 시각을 본다
        procs = [subprocess.Popen([sys.executable, "-c", CHILD, kit.REPO, "race", root, "K", str(seq), str(start)], stdout=subprocess.PIPE,
                                  text=True) for _ in range(6)]
        self.assertEqual(sorted(p.communicate(timeout=60)[0].strip() for p in procs), ["True"] * 6)  # 모두 ok(하나는 새 취소, 나머지 already)
        self.assertEqual((len(events(root, "cancel", budget.BUDGET)), _week(root)), (1, 0))
        for i in range(17):
            budget.charge(root, "experiment", 1, WED + 1 + i, key="exp-%d" % i)
        procs = [subprocess.Popen([sys.executable, "-c", CHILD, kit.REPO, "charge", root, "p-%d" % i, str(WED + 50)], stdout=subprocess.PIPE,
                                  text=True) for i in range(8)]
        self.assertEqual(sorted(p.communicate(timeout=60)[0].strip() for p in procs).count("True"), 3)
        self.assertEqual(_week(root), 20)
        self.assertIn(opstate.BUDGET_EXCEEDED, opstate.load(root)["conditions"])


if __name__ == "__main__":
    unittest.main()
