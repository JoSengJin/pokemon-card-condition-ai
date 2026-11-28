"""승격·복원·계보 무효화(철회) 중 지점을 정해 실제 kill -9(SIGKILL)를 맞는 시험. 어느 지점에서도 포인터는 이전 또는 새 Champion을 완전히 가리킨다.

합성 시험이며 모델 성능 근거가 아니다. 하위 프로세스 스크립트(KILL)는 support에 있고 지정한 지점에서 스스로 SIGKILL을 보낸다.
"""
import unittest

import json

from harness import champion, registry, withdrawal
from tests.test_harness_champion_support import add_model, assert_consistent, kill_at, make_root, pointer_model, read_events
from tests.test_harness_withdrawal_support import make_batch

POINTS = ("before_intent", "after_intent", "before_pointer_fsync", "before_replace", "after_replace", "after_switched",
          "after_main_ledger")
RESTORE_POINTS = POINTS + ("before_materialize_replace",)
NEW_POINTER = ("after_replace", "after_switched", "after_main_ledger")  # os.replace가 끝난 뒤의 지점


class KillPointsTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.a, self.b = add_model(self.root, "a"), add_model(self.root, "b")

    def count(self, event):
        return len([e for e in read_events(self.root) if e["event"] == event])

    def test_kill_while_replacing_an_existing_champion(self):
        for point in POINTS:
            with self.subTest(point):
                self.setUp()
                champion.promote(self.root, 2.0, self.a)
                kill_at(self, self.root, point, "promote", self.b)
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
                kill_at(self, self.root, point, "promote", self.a)
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
                kill_at(self, self.root, point, "restore", self.b)
                want = self.a if point in NEW_POINTER else self.b
                self.assertEqual(want, pointer_model(self.root))
                state = registry.load(self.root)
                self.assertEqual("invalidated", state["models"][self.b]["status"])  # 회귀 기록은 전환보다 먼저 남는다
                self.assertIn(pointer_model(self.root), {self.a, self.b})
                res = champion.restore_last_verified(self.root, 10.0, regression="killed regression", model_id=self.b)  # 같은 인자 재호출
                self.assertEqual(self.a, pointer_model(self.root))
                self.assertTrue(res["ok"] or res["reason"] == "champion_valid")
                self.assertEqual("valid", registry.load(self.root)["models"][self.a]["status"])  # 복원한 Champion을 무효화하지 않았다
                state = assert_consistent(self, self.root, {self.a})
                self.assertIsNone(state["pending"])
                self.assertEqual([self.a, self.b, self.a], [h["model_id"] for h in state["history"]])


    def test_kill_during_lineage_invalidation_then_same_call_again_finishes_the_restore(self):
        for point in ("before_invalidated", "after_invalidated") + RESTORE_POINTS:
            with self.subTest(point):
                self.setUp()
                kw = {"policy_id": make_batch(self.root, "s1"), "reason": "contamination", "batches": ["s1"]}
                bad = add_model(self.root, "bad", batches=["s1"])
                champion.promote(self.root, 2.0, self.a)
                self.assertTrue(champion.promote(self.root, 3.0, bad)["ok"])
                kill_at(self, self.root, point, "withdraw", json.dumps(kw))
                want = self.a if point in NEW_POINTER else bad
                self.assertEqual(want, pointer_model(self.root))
                champion.current(self.root, registry.load(self.root))  # 포인터가 마지막 전환과 맞다(거짓 오류·변조 오류 없음)
                res = withdrawal.withdraw(self.root, 10.0, **kw)  # 이미 무효여도(새로 무효화할 모델이 없어도) 복원을 이어간다
                self.assertEqual(self.a, pointer_model(self.root))
                self.assertTrue(res["restore"] is None or res["restore"]["ok"] or res["restore"]["reason"] == "champion_valid")
                state = registry.load(self.root)
                self.assertTrue(champion.current(self.root, state)["valid"])
                self.assertIsNone(state["pending"])
                self.assertEqual("invalidated", state["models"][bad]["status"])
                self.assertEqual([self.a, bad, self.a], [h["model_id"] for h in state["history"]])


if __name__ == "__main__":
    unittest.main()
