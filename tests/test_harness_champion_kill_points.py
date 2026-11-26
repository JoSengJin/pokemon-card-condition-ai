"""승격·복원 중 지점을 정해 실제 kill -9(SIGKILL)를 맞는 시험. 어느 지점에서도 포인터는 이전 또는 새 Champion을 완전히 가리킨다.

합성 시험이며 모델 성능 근거가 아니다. 하위 프로세스가 ledger.append·os.replace·os.fsync를 감싸 지정한 지점에서 스스로 SIGKILL을 보낸다.
"""
import signal
import unittest

from harness import champion, registry
from tests.test_harness_champion_support import add_model, assert_consistent, make_root, pointer_model, read_events, run_py

KILL = r'''
import os, signal, sys
from harness import champion, ledger
root, model, point, mode = sys.argv[1:5]
real_append, real_replace, real_fsync = ledger.append, os.replace, os.fsync
armed = {"on": False}
def die():
    os.kill(os.getpid(), signal.SIGKILL)
def append(path, ts, event, data):
    if point == "before_intent" and event == "switch_intent":
        die()
    entry = real_append(path, ts, event, data)
    armed["on"] = armed["on"] or event == "switch_intent"
    if (point, event) in (("after_intent", "switch_intent"), ("after_switched", "switched"),
                          ("after_main_ledger", "champion_promoted"), ("after_main_ledger", "champion_restored")):
        die()
    return entry
def replace(src, dst):
    if point == "before_materialize_replace" and dst.endswith("weights"):  # 복원 중 CAS 꺼내기
        die()
    if not dst.endswith("champion.json"):
        return real_replace(src, dst)
    if point == "before_replace":
        die()
    real_replace(src, dst)
    if point == "after_replace":
        die()
def fsync(fd):
    if point == "before_pointer_fsync" and armed["on"]:
        die()
    real_fsync(fd)
ledger.append, os.replace, os.fsync = append, replace, fsync
if mode == "promote":
    champion.promote(root, 9.0, model)
else:
    champion.restore_last_verified(root, 9.0, regression="killed regression")
print("SURVIVED")
'''
POINTS = ("before_intent", "after_intent", "before_pointer_fsync", "before_replace", "after_replace", "after_switched",
          "after_main_ledger")
RESTORE_POINTS = POINTS + ("before_materialize_replace",)
NEW_POINTER = ("after_replace", "after_switched", "after_main_ledger")  # os.replace가 끝난 뒤의 지점


class KillPointsTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.a, self.b = add_model(self.root, "a"), add_model(self.root, "b")

    def kill_at(self, point, mode, model):
        proc = run_py(KILL, self.root, model, point, mode)
        self.assertEqual(-signal.SIGKILL, proc.returncode, (point, proc.stdout, proc.stderr))
        self.assertNotIn("SURVIVED", proc.stdout)

    def count(self, event):
        return len([e for e in read_events(self.root) if e["event"] == event])

    def test_kill_while_replacing_an_existing_champion(self):
        for point in POINTS:
            with self.subTest(point):
                self.setUp()
                champion.promote(self.root, 2.0, self.a)
                self.kill_at(point, "promote", self.b)
                want = self.b if point in NEW_POINTER else self.a
                self.assertEqual(want, pointer_model(self.root))  # 이전 또는 새 Champion 하나를 완전히 가리킨다
                assert_consistent(self, self.root, {self.a, self.b})
                retry = champion.promote(self.root, 10.0, self.b)
                self.assertTrue(retry["ok"])
                state = assert_consistent(self, self.root, {self.b})
                self.assertEqual(self.b, pointer_model(self.root))
                self.assertIsNone(state["pending"])
                self.assertEqual([self.a, self.b], [h["model_id"] for h in state["history"]])
                self.assertEqual(2, self.count("switched"))  # 재시도가 한 번 더 전환하지 않았다
                self.assertEqual(1 if point in ("after_intent", "before_pointer_fsync", "before_replace") else 0,
                                 self.count("switch_aborted"))

    def test_kill_during_the_first_promotion(self):
        for point in POINTS:
            with self.subTest(point):
                self.setUp()
                self.kill_at(point, "promote", self.a)
                assert_consistent(self, self.root, {None, self.a})
                self.assertEqual(self.a if point in NEW_POINTER else None, pointer_model(self.root))
                self.assertTrue(champion.promote(self.root, 10.0, self.a)["ok"])
                self.assertEqual(self.a, pointer_model(self.root))
                self.assertEqual(1, self.count("switched"))

    def test_kill_during_restore_leaves_old_or_restored_champion_and_retry_finishes(self):
        for point in RESTORE_POINTS:
            with self.subTest(point):
                self.setUp()
                champion.promote(self.root, 2.0, self.a)
                champion.promote(self.root, 3.0, self.b)
                self.kill_at(point, "restore", self.b)
                want = self.a if point in NEW_POINTER else self.b
                self.assertEqual(want, pointer_model(self.root))
                state = registry.load(self.root)
                self.assertEqual("invalidated", state["models"][self.b]["status"])  # 회귀 기록은 전환보다 먼저 남는다
                self.assertIn(pointer_model(self.root), {self.a, self.b})
                res = champion.restore_last_verified(self.root, 10.0)
                self.assertEqual(self.a, pointer_model(self.root))
                self.assertTrue(res["ok"] or res["reason"] == "champion_valid")
                state = assert_consistent(self, self.root, {self.a})
                self.assertIsNone(state["pending"])
                self.assertEqual([self.a, self.b, self.a], [h["model_id"] for h in state["history"]])


if __name__ == "__main__":
    unittest.main()
