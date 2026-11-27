"""복원: 무효 Champion을 마지막 검증된 Champion으로 되돌리고 CAS 가중치 해시를 재현한다. 합성 시험이며 모델 성능 근거가 아니다."""
import hashlib
import os
import unittest
from unittest import mock

from harness import cas, champion, registry
from tests.test_harness_champion_support import add_model, bad_copy, make_root, pointer_model, read_events


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.ids = [add_model(self.root, n) for n in "abc"]
        self.cas_root = os.path.join(self.root, "cas")

    def promote_all(self, count):
        for i, model in enumerate(self.ids[:count]):
            self.assertTrue(champion.promote(self.root, 2.0 + i, model)["ok"])

    def test_regression_restores_previous_champion_and_reproduces_weights_hash(self):
        a, b = self.ids[:2]
        self.promote_all(2)
        res = champion.restore_last_verified(self.root, 5.0, regression="seal recheck failed", model_id=b)
        self.assertTrue(res["ok"])
        self.assertEqual((a, b, True), (res["model_id"], res["restored_from"], res["reproduced"]))
        self.assertEqual(a, pointer_model(self.root))
        with open(res["weights_path"], "rb") as handle:
            self.assertEqual(hashlib.sha256(b"weights-a").hexdigest(), hashlib.sha256(handle.read()).hexdigest())
        self.assertEqual(res["weights_sha"], registry.load(self.root)["models"][a]["weights_sha"])
        again = champion.restore_last_verified(self.root, 5.5, regression="seal recheck failed", model_id=b)  # 같은 인자 재호출
        self.assertEqual((False, "champion_valid"), (again["ok"], again["reason"]))
        self.assertEqual("valid", registry.load(self.root)["models"][a]["status"])  # 복원한 정상 Champion을 무효화하지 않는다
        with self.assertRaises(champion.ChampionError):  # 무효화 대상 모델 ID 없이 regression만 주면 거절
            champion.restore_last_verified(self.root, 6.0, regression="x")
        state = registry.load(self.root)
        self.assertEqual("invalidated", state["models"][b]["status"])
        self.assertIn("regression: seal recheck failed", state["models"][b]["causes"])
        self.assertEqual("champion_restored", read_events(self.root, "ledger.jsonl")[-1]["event"])


    def test_restore_walks_back_one_valid_champion_at_a_time(self):
        a, b, c = self.ids
        self.promote_all(3)
        self.assertEqual(b, champion.restore_last_verified(self.root, 5.0, regression="r1", model_id=c)["model_id"])
        self.assertEqual(a, champion.restore_last_verified(self.root, 6.0, regression="r2", model_id=b)["model_id"])
        last = champion.restore_last_verified(self.root, 7.0, regression="r3", model_id=a)  # 더 돌아갈 곳이 없다
        self.assertEqual((False, "no_verified_champion"), (last["ok"], last["reason"]))
        state = registry.load(self.root)
        self.assertEqual(a, pointer_model(self.root))
        self.assertFalse(champion.current(self.root, state)["valid"])  # 무효인 채 남았음을 숨기지 않는다

    def test_damaged_cas_blob_raises_and_leaves_pointer_unchanged(self):
        a, b = self.ids[:2]
        self.promote_all(2)
        blob = cas.blob_path(self.cas_root, registry.load(self.root)["models"][a]["weights_sha"])
        with open(blob, "ab") as handle:
            handle.write(b"x")
        with self.assertRaises(champion.ChampionError):
            champion.restore_last_verified(self.root, 5.0, regression="r", model_id=b)
        self.assertEqual(b, pointer_model(self.root))
        self.assertIsNone(registry.load(self.root)["pending"])
        self.assertEqual("invalidated", read_events(self.root)[-1]["event"])  # 전환 의도조차 쓰지 않았다

    def test_copy_with_a_different_hash_than_recorded_is_an_error(self):
        a, b = self.ids[:2]
        self.promote_all(2)

        with mock.patch.object(cas, "get", lambda cas_root, sha, dest: bad_copy(dest)):  # 복사본이 기록된 해시와 다름
            with self.assertRaises(champion.ChampionError):
                champion.restore_last_verified(self.root, 5.0, regression="r", model_id=b)
        self.assertEqual(b, pointer_model(self.root))
        self.assertFalse(os.path.exists(os.path.join(self.root, "models", "restored", a, "weights")))

    def test_no_champion_is_reported_and_restore_after_restore_does_nothing(self):
        a, b, c = self.ids
        self.assertEqual("no_champion", champion.restore_last_verified(self.root, 2.0)["reason"])
        self.promote_all(2)
        champion.restore_last_verified(self.root, 5.0, regression="r", model_id=b)
        events = read_events(self.root)
        again = champion.restore_last_verified(self.root, 6.0)
        self.assertEqual("champion_valid", again["reason"])
        self.assertEqual(events, read_events(self.root))
        self.assertEqual("champion_valid", champion.restore_last_verified(self.root, 6.5)["reason"])  # 유효하면 건드리지 않는다
        self.assertTrue(champion.promote(self.root, 7.0, c)["ok"])
        self.assertEqual(c, pointer_model(self.root))


if __name__ == "__main__":
    unittest.main()
