"""감사 대기 시험: 계보의 Silver 묶음 감사가 끝나기 전에는 승격하지 않는다(DESIGN 5-4). 합성 시험이다.

2026-11-27 철회 보완: 승격은 호출자가 준 audit_status를 받지 않고 Silver 장부를 잠금 안에서 직접 읽는다. 그래서 이 시험은 실제 장부에
감사 상태를 만들고(make_batch) 승격을 부른다. 예전의 "장부에 없는 묶음 = audit_pending" 기대는, 그런 묶음을 선언한 모델의 학습 manifest가
장부와 맞지 않으므로 manifest 대조에서 먼저 막히는 것으로 바뀌었다(eligibility 시험).
"""
import unittest

from harness import champion
from tests.test_harness_champion_support import add_model, make_root, pointer_model, read_events
from tests.test_harness_withdrawal_support import OTHER, make_batch


class AuditGateTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)

    def refuse(self, model, reason):
        before = read_events(self.root)
        res = champion.promote(self.root, 2.0, model)
        self.assertEqual((False, reason), (res["ok"], res["reason"]))
        self.assertIsNone(pointer_model(self.root))
        self.assertEqual(before, read_events(self.root))  # 거절은 아무 것도 쓰지 않는다
        return res

    def test_unplanned_planned_or_partial_audit_is_refused_as_audit_pending(self):
        for state in ("unplanned", "planned", "partial"):
            with self.subTest(state):
                make_batch(self.root, "s-" + state, state)
                res = self.refuse(add_model(self.root, "m-" + state, batches=["s-" + state]), "audit_pending")
                self.assertEqual({"s-" + state: "pending"}, res["detail"])
        make_batch(self.root, "s1")
        both = add_model(self.root, "both", batches=["s1", "s-partial"])  # 하나는 완료, 하나는 대기
        self.assertEqual({"s-partial": "pending"}, self.refuse(both, "audit_pending")["detail"])

    def test_failed_audit_is_refused_even_if_the_other_batch_is_complete(self):
        make_batch(self.root, "s1")
        make_batch(self.root, "s2", "failed")
        res = self.refuse(add_model(self.root, "m", batches=["s1", "s2"]), "audit_failed")
        self.assertEqual({"s2": "failed"}, res["detail"])

    def test_complete_or_not_required_audits_pass(self):
        make_batch(self.root, "s1", scope=OTHER)
        make_batch(self.root, "s2", "not_required", scope=OTHER)
        model = add_model(self.root, "m", batches=["s1", "s2"])
        self.assertTrue(champion.promote(self.root, 3.0, model)["ok"])
        self.assertEqual(model, pointer_model(self.root))

    def test_ancestor_batch_audit_is_required_for_the_child(self):
        make_batch(self.root, "s1")
        make_batch(self.root, "s2", "partial")
        make_batch(self.root, "s3")
        parent = add_model(self.root, "parent", batches=["s1", "s2"])
        child = add_model(self.root, "child", batches=["s3"], parent=parent)
        self.assertEqual({"s2": "pending"}, self.refuse(child, "audit_pending")["detail"])  # 부모의 s2가 대기

    def test_promote_takes_no_audit_status_and_a_model_without_silver_needs_no_audit(self):
        make_batch(self.root, "s1", "planned")
        model = add_model(self.root, "m", batches=["s1"])
        with self.assertRaises(TypeError):  # 호출자가 준 감사 상태로 승격을 완화할 길이 없다
            champion.promote(self.root, 2.0, model, {"s1": "complete"})
        self.refuse(model, "audit_pending")
        self.assertTrue(champion.promote(self.root, 2.0, add_model(self.root, "plain"))["ok"])


if __name__ == "__main__":
    unittest.main()
