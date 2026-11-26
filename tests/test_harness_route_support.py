import subprocess
import unittest

from harness import route
from tests.test_harness_route_fixtures import HELP, contract, decision, policy


def run_ok(text, code=0):
    calls = []

    def run(argv):
        calls.append(argv)
        return code, text
    run.calls = calls
    return run


class SupportTest(unittest.TestCase):
    def test_probe_reads_options_and_lists_from_help_without_other_commands(self):
        run = run_ok(HELP)
        got = route.probe_cli_support(run=run)
        self.assertEqual(run.calls, [["claude", "--help"]])  # 모델 호출·-p 실행 없음
        self.assertEqual((got["status"], got["model_option"], got["effort_option"]), ("ok", True, True))
        self.assertEqual(got["effort_levels"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(got["model_examples"], ["fable", "opus", "sonnet"])

    def test_probe_failures_are_reported_not_hidden(self):
        def missing(argv):
            raise FileNotFoundError("claude")

        def slow(argv):
            raise subprocess.TimeoutExpired(argv, 30)
        for name, run in {"실행 파일 없음": missing, "시간 초과": slow, "비정상 종료": run_ok(HELP, 2),
                          "빈 출력": run_ok("  \n")}.items():
            with self.subTest(name):
                got = route.probe_cli_support(run=run)
                self.assertEqual(got["status"], "failed")
                self.assertTrue(got["error"])
                self.assertEqual((got["model_option"], got["effort_option"]), (None, None))

    def test_ok_support_records_applied_unverified_and_haiku_unconfirmed(self):
        support = route.probe_cli_support(run=run_ok(HELP))
        sonnet = route.with_support(decision("general_dev"), support)
        self.assertEqual(sonnet["applied"], {"model": "sonnet", "effort": "medium", "verified": False})
        self.assertEqual(len(sonnet["limitations"]), 1)
        self.assertTrue(sonnet["limitations"][0].startswith("actual_application_unverified"))
        haiku = route.with_support(decision("experiment_log_summary"), support)
        self.assertEqual((haiku["applied"]["model"], haiku["applied"]["effort"]), ("haiku", "low"))
        self.assertTrue(any(x.startswith("model_value_unconfirmed") and "haiku" in x for x in haiku["limitations"]))
        self.assertFalse(haiku["applied"]["verified"])

    def test_missing_options_are_not_silently_ignored(self):
        no_opts = route.probe_cli_support(run=run_ok("Options:\n  --help   Show help\n"))
        self.assertEqual((no_opts["status"], no_opts["model_option"], no_opts["effort_option"]), ("ok", False, False))
        got = route.with_support(decision("label_disagreement"), no_opts)
        self.assertEqual((got["applied"]["model"], got["applied"]["effort"]), (None, None))
        codes = [x.split(":")[0] for x in got["limitations"]]
        self.assertIn("model_option_missing", codes)
        self.assertIn("effort_option_missing", codes)
        self.assertEqual((got["model"], got["effort"]), ("opus", "high"))  # 요청값은 그대로 남는다

    def test_unsupported_effort_value_and_unlisted_levels_and_xhigh(self):
        old = HELP.replace("(low, medium, high, xhigh, max)", "(low, medium, high)")
        support = route.probe_cli_support(run=run_ok(old))
        up = route.escalate(decision("label_disagreement"), {"cause": "quality_gate_miss"},
                            xhigh_justified=True, budget_remaining=1)
        got = route.with_support(up, support)
        self.assertEqual((got["applied"]["model"], got["applied"]["effort"]), ("opus", None))
        self.assertTrue(any(x.startswith("effort_value_unsupported") and "xhigh" in x for x in got["limitations"]))
        ok = route.with_support(up, route.probe_cli_support(run=run_ok(HELP)))
        self.assertEqual(ok["applied"]["effort"], "xhigh")
        self.assertTrue(any(x.startswith("xhigh_model_combo_unconfirmed") for x in ok["limitations"]))
        nolist = route.probe_cli_support(run=run_ok(HELP.replace("(low, medium, high, xhigh, max)", "")))
        unconfirmed = route.with_support(decision("general_dev"), nolist)
        self.assertTrue(any(x.startswith("effort_values_unconfirmed") for x in unconfirmed["limitations"]))

    def test_probe_failure_leaves_nothing_applied(self):
        failed = route.probe_cli_support(run=run_ok("", 1))
        got = route.with_support(decision("silver_labeling"), failed)
        self.assertEqual(got["applied"], {"model": None, "effort": None, "verified": False})
        self.assertTrue(any(x.startswith("cli_probe_failed") for x in got["limitations"]))
        self.assertTrue(any(x.startswith("actual_application_unverified") for x in got["limitations"]))

    def test_no_llm_decision_has_nothing_to_apply(self):
        got = route.with_support(route.route(contract("deterministic", needs_llm=False), [], policy()),
                                 route.probe_cli_support(run=run_ok(HELP)))
        self.assertEqual(got["applied"], {"model": None, "effort": None, "verified": None})
        self.assertEqual(got["limitations"], [])


if __name__ == "__main__":
    unittest.main()
