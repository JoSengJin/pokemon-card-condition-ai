"""계보 무효화: Silver 묶음을 쓴 모델과 후속만 무효, 무관한 모델 유지, Champion 포함 시 자동 복원. 합성 시험이다.

2026-11-27 철회 보완: 묶음 계보 무효화의 입구는 정책 철회 관문 하나(withdrawal.withdraw)다(옛 lineage.invalidate_lineage는 없앴다:
철회 없이 묶음만 무효화하는 다른 경로를 두지 않는다). 그래서 실제 Silver 장부에 묶음을 만들고 철회로 무효화한다.
"""
import unittest

from harness import champion, registry, silver_policy, withdrawal
from tests.test_harness_champion_support import add_model, make_root, pointer_model, read_events
from tests.test_harness_withdrawal_support import OTHER, make_batch


class LineageTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = make_batch(self.root, "s1")                                 # 정책 P의 유일한 묶음
        make_batch(self.root, "s9", scope=OTHER)                                  # 다른 정책 Q
        make_batch(self.root, "s2", scope=OTHER)
        self.base = add_model(self.root, "base")                                  # 묶음 없음(안전한 이전 Champion 후보)
        self.r = add_model(self.root, "r", batches=["s1"])                        # s1 직접 사용
        self.c = add_model(self.root, "c", parent=self.r)                         # r의 후속
        self.g = add_model(self.root, "g", parent=self.c, batches=["s9"])         # 손자
        self.u = add_model(self.root, "u", batches=["s2"])                        # 무관
        self.p = add_model(self.root, "p", parent=self.u)                         # 무관 후속
        self.args = (self.policy, "batch_label_error", ["s1"])                    # 수동 철회: s1의 라벨 오류

    def status(self, model_id):
        return registry.load(self.root)["models"][model_id]["status"]

    def test_direct_and_all_descendants_are_invalidated_and_unrelated_models_stay(self):
        res = withdrawal.withdraw(self.root, 2.0, *self.args)
        self.assertEqual(sorted([self.r, self.c, self.g]), res["invalidated"])
        self.assertIsNone(res["restore"])
        for model in (self.r, self.c, self.g):
            self.assertEqual("invalidated", self.status(model), model)
        for model in (self.base, self.u, self.p):
            self.assertEqual("valid", self.status(model), model)
        self.assertEqual(1, len([e for e in read_events(self.root) if e["event"] == "invalidated"]))  # 한 이벤트
        for model in (self.r, self.c, self.g):  # 무효가 된 계보 구성원은 이후 승격도 거절된다
            res = champion.promote(self.root, 3.0, model)
            self.assertEqual((False, "invalidated"), (res["ok"], res["reason"]), model)
        self.assertIsNone(pointer_model(self.root))
        self.assertTrue(champion.promote(self.root, 4.0, self.p)["ok"])  # 무관 후속은 영향 없음

    def test_champion_in_lineage_is_restored_to_the_last_verified_champion(self):
        champion.promote(self.root, 2.0, self.base)
        self.assertTrue(champion.promote(self.root, 3.0, self.g)["ok"])
        res = withdrawal.withdraw(self.root, 4.0, *self.args)
        self.assertEqual((True, self.base, self.g), (res["restore"]["ok"], res["restore"]["model_id"], res["restore"]["restored_from"]))
        self.assertEqual(self.base, pointer_model(self.root))
        self.assertTrue(champion.current(self.root, registry.load(self.root))["valid"])
        self.assertEqual("champion_restored", read_events(self.root, "ledger.jsonl")[-1]["event"])

    def test_unrelated_champion_keeps_the_pointer_and_nothing_is_restored(self):
        champion.promote(self.root, 2.0, self.u)
        res = withdrawal.withdraw(self.root, 3.0, *self.args)
        self.assertEqual((None, None), (res["restore"], res["conditional"]))  # 다른 정책이라 조건부 유지도 아니다
        self.assertEqual(self.u, pointer_model(self.root))
        self.assertEqual(1, len(registry.load(self.root)["history"]))

    def test_repeating_writes_nothing_and_a_batch_outside_the_policy_is_refused(self):
        withdrawal.withdraw(self.root, 2.0, *self.args)
        events = read_events(self.root)
        again = withdrawal.withdraw(self.root, 3.0, *self.args)
        self.assertEqual((True, []), (again["already"], again["invalidated"]))
        self.assertEqual([], withdrawal.withdraw(self.root, 3.0)["invalidated"])  # 복구만 호출
        self.assertEqual(events, read_events(self.root))
        for batches in (["no-such-batch"], ["s9"], [""], []):
            with self.assertRaises(silver_policy.PolicyError, msg=batches):
                withdrawal.withdraw(self.root, 4.0, self.policy, "batch_label_error", batches)

    def test_descendants_of_an_already_invalid_model_are_still_reached(self):
        champion.promote(self.root, 2.0, self.base)
        self.assertTrue(champion.promote(self.root, 3.0, self.c)["ok"])
        champion.restore_last_verified(self.root, 4.0, regression="c regressed", model_id=self.c)  # c만 회귀 무효, r·g는 유효
        self.assertEqual(("invalidated", "valid", "valid"), (self.status(self.c), self.status(self.r), self.status(self.g)))
        res = withdrawal.withdraw(self.root, 5.0, *self.args)
        self.assertEqual(sorted([self.r, self.g]), res["invalidated"])  # c는 이미 무효, 그 후속 g는 따라간다


if __name__ == "__main__":
    unittest.main()
