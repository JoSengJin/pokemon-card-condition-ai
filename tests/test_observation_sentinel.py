import unittest
from readiness_fixture import matrix, rec, role_contract
from card_condition.observation_roles import PHASES, SENTINEL_SCENARIOS, sentinel_status, sentinel_verdict


class SentinelTests(unittest.TestCase):
    def test_mock_results_do_not_verify_actual_access(self):
        r = sentinel_status(matrix(), role_contract("mock_denial", "x"))
        self.assertEqual((r["status"], r["actual_access_verified"]), ("blocked_unverified", False))
        self.assertEqual(len(r["missing"]), len(SENTINEL_SCENARIOS) * len(PHASES))
        self.assertEqual(sentinel_verdict(rec("tool_bypass", "before_release")), "mock_pass")

    def test_forbidden_access_or_marker_reply_fails(self):
        for scenario in ("forbidden_direct_file", "tool_bypass", "reply_leak", "memory_leak", "conversation_leak"):
            for mode, same in (("mock", None), ("actual_identity", False)):
                v = sentinel_verdict(rec(scenario, "after_release", mode, actual="allow", run_identity="id-1",
                                         same_os_user_as_protected=same))
                self.assertEqual(v, "fail")
        r = sentinel_status([rec("reply_leak", "after_quarantine", actual="allow")], role_contract())
        self.assertEqual(r["status"], "failed")

    def test_same_os_user_denial_stays_unverified(self):
        for same in (True, None):
            v = sentinel_verdict(rec("forbidden_direct_file", "before_release", "actual_identity", run_identity="id-1",
                                     same_os_user_as_protected=same))
            self.assertEqual(v, "unverified")
        self.assertEqual(sentinel_verdict(rec("forbidden_direct_file", "before_release", "actual_identity")), "unverified")
        self.assertEqual(sentinel_verdict(rec("allowed_access", "before_release", actual=None)), "unverified")

    def test_real_marker_and_mode_mismatch_rejected(self):
        for bad in (dict(marker="real-secret"), dict(evidence_type="real_permission_env"), dict(data_origin="real_files")):
            with self.assertRaises(ValueError):
                sentinel_verdict(rec("allowed_access", "before_release", **bad))
        with self.assertRaises(ValueError):
            sentinel_verdict(rec("allowed_access", "before_release", actual=None, null_reason=None))

    def test_enforcement_kind_gates_review_readiness_and_never_verifies(self):
        passing = matrix(mode="actual_identity", run_identity="id-1", same_os_user_as_protected=False)
        for kind, mech in ((None, None), ("same_privilege_subagent", "x"), ("mock_denial", "x"), ("external_enforcer", None)):
            self.assertEqual(sentinel_status(passing, role_contract(kind, mech))["status"], "blocked_unverified")
        r = sentinel_status(passing, role_contract("distinct_os_identity", "fixture-mechanism"))
        self.assertEqual((r["status"], r["actual_access_verified"], r["independent_evaluation_claim"], r["collection_ready"]),
                         ("evidence_ready_for_review", False, False, False))
        self.assertEqual(sentinel_status(passing[:-1], role_contract("distinct_os_identity", "m"))["status"], "blocked_unverified")
