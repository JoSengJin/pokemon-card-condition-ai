"""감사 대기 시험: 계보의 Silver 묶음 감사가 끝나기 전에는 승격하지 않는다(DESIGN 5-4). 합성 시험이다."""
import unittest

from harness import champion
from tests.test_harness_champion_support import add_model, make_root, pointer_model, read_events


class AuditGateTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.m = add_model(self.root, "m", batches=["s1", "s2"])

    def refuse(self, status, reason):
        before = read_events(self.root)
        res = champion.promote(self.root, 2.0, self.m, status)
        self.assertEqual((False, reason), (res["ok"], res["reason"]))
        self.assertIsNone(pointer_model(self.root))
        self.assertEqual(before, read_events(self.root))  # 거절은 아무 것도 쓰지 않는다
        return res

    def test_missing_pending_or_partial_audit_is_refused_as_audit_pending(self):
        self.refuse(None, "audit_pending")
        self.refuse({}, "audit_pending")
        self.refuse({"s1": "pending", "s2": "pending"}, "audit_pending")
        res = self.refuse({"s1": "complete"}, "audit_pending")  # s2 누락
        self.assertEqual({"s2": None}, res["detail"])

    def test_failed_audit_is_refused_even_if_the_other_batch_is_complete(self):
        res = self.refuse({"s1": "complete", "s2": "failed"}, "audit_failed")
        self.assertEqual({"s2": "failed"}, res["detail"])

    def test_complete_or_not_required_audits_pass_and_retry_succeeds_after_refusal(self):
        self.refuse({"s1": "complete", "s2": "pending"}, "audit_pending")
        res = champion.promote(self.root, 3.0, self.m, {"s1": "complete", "s2": "not_required"})
        self.assertTrue(res["ok"])
        self.assertEqual(self.m, pointer_model(self.root))

    def test_ancestor_batch_audit_is_required_for_the_child(self):
        child = add_model(self.root, "child", batches=["s3"], parent=self.m)
        res = champion.promote(self.root, 2.0, child, {"s3": "complete", "s1": "complete"})  # 부모의 s2 누락
        self.assertEqual(("audit_pending", {"s2": None}), (res["reason"], res["detail"]))
        ok = champion.promote(self.root, 3.0, child, {"s1": "complete", "s2": "complete", "s3": "complete"})
        self.assertTrue(ok["ok"])

    def test_model_without_silver_batches_needs_no_audit_status_and_audit_status_must_be_a_dict(self):
        with self.assertRaises(champion.ChampionError):
            champion.promote(self.root, 2.0, self.m, ["s1", "s2"])
        plain = add_model(self.root, "plain")
        self.assertTrue(champion.promote(self.root, 2.0, plain)["ok"])


if __name__ == "__main__":
    unittest.main()
