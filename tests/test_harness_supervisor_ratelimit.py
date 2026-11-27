"""한도 이벤트 해석(ratelimit)과 claude 인자(claude_run): 재개 시각 형식, 단기/주간/미상, 한도 판정, --continue·금지 명령 미사용."""
import ast
import json
import os
import unittest

from harness import claude_run, ratelimit
from tests.test_harness_supervisor_kit import make_fake, runs

T = 1764200000.0  # 2025-11-26T23:33:20Z
HARNESS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness")
NEW = ("supervisor", "opstate", "ratelimit", "claude_run", "claude_job", "budget", "unlock")


def lines(*events):
    return [json.dumps(e) for e in events]


class RateLimitTest(unittest.TestCase):
    def test_parse_reset_accepts_seconds_ms_iso_and_rejects_the_rest(self):
        for value in (T, int(T), T * 1000, str(int(T)), "%d" % (T * 1000), "2025-11-26T23:33:20Z",
                      "2025-11-27T08:33:20+09:00", "2025-11-26T23:33:20.000+00:00"):
            self.assertEqual(ratelimit.parse_reset(value), T, value)
        for value in (None, True, False, "", "soon", "2025-11-26T23:33:20", 120, 0, -5, "-5", float("inf"),
                      float("nan"), {"a": 1}, [T], 1e17):
            self.assertIsNone(ratelimit.parse_reset(value), value)

    def test_kind_from_event_fields_only(self):
        self.assertEqual([ratelimit.classify_kind(v) for v in ("five_hour", "seven_day", "seven_day_opus", None, "hourly", 5)],
                         ["short", "weekly", "weekly", "unknown", "unknown", "unknown"])
        nested = ratelimit.scan(lines({"type": "rate_limit_event", "rate_limit_info": {"resetsAtSeconds": T, "rateLimitType": "seven_day"}}), 1)
        top = ratelimit.scan(lines({"type": "rate_limit_event", "resetsAt": T * 1000, "status": "rejected"}), 1)
        self.assertEqual((nested["rate_limit"]["kind"], nested["rate_limit"]["resets_at"]), ("weekly", T))
        self.assertEqual((top["rate_limit"]["kind"], top["rate_limit"]["resets_at"]), ("unknown", T))  # 단기로 두지 않는다

    def test_limited_rules(self):
        init = {"type": "system", "subtype": "init", "session_id": "s-1", "model": "claude-sonnet-x"}
        ok = {"type": "result", "subtype": "success", "is_error": False}
        bad = {"type": "result", "subtype": "error", "is_error": True}
        cases = [("rejected", ok, 0, True), ("allowed", ok, 0, False), ("allowed_warning", bad, 1, False),
                 (None, bad, 1, True), (None, ok, 0, False), ("rejected", None, 0, True)]
        for status, result, code, want in cases:
            event = {"type": "rate_limit_event", "rate_limit_info": {"status": status, "resetsAt": T}}
            found = ratelimit.scan(lines(init, event, *([result] if result else [])) + ["not json", "[1]"], code)
            self.assertEqual(found["limited"], want, (status, result, code))
            self.assertEqual((found["session_id"], found["init"]["model"], found["init"]["effort"], found["bad_lines"]),
                             ("s-1", "claude-sonnet-x", None, 2))
        self.assertFalse(ratelimit.scan(lines(init, bad), 1)["limited"])  # 이벤트 없는 실패는 한도가 아니다
        self.assertTrue(ratelimit.scan(lines(init, ok), 0)["success"])
        self.assertFalse(ratelimit.scan(lines(init, ok), 1)["success"])

    def test_argv_has_no_continue_and_refuses_forbidden_commands(self):
        new = claude_run.build_argv("claude", "작업", "sonnet", "medium", session_id="u-1")
        old = claude_run.build_argv("claude", "작업", "opus", "high", resume="u-1")
        self.assertEqual(new[1:], ["-p", "작업", "--output-format", "stream-json", "--verbose", "--model", "sonnet",
                                   "--effort", "medium", "--session-id", "u-1"])
        self.assertEqual(old[-2:], ["--resume", "u-1"])
        for argv in (new, old):
            self.assertFalse({"--continue", "-c"} & set(argv))
        bad_calls = [("/low-priority", "sonnet", {"session_id": "u"}), (" /rate-limit-options now", "sonnet", {"session_id": "u"}),
                     ("", "sonnet", {"session_id": "u"}), ("작업", "sonnet", {"resume": "a", "session_id": "b"}),
                     ("작업", "sonnet", {}), ("작업", None, {"session_id": "u"})]
        for prompt, model, kw in bad_calls:
            with self.assertRaises(ValueError, msg=(prompt, model, kw)):
                claude_run.build_argv("claude", prompt, model, "medium", **kw)
        self.assertEqual(claude_run.CONTINUE_WINDOW_HOURS, 4)

    def test_forbidden_strings_only_in_guard_constants(self):
        for name in NEW:
            with open(os.path.join(HARNESS, name + ".py"), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            guards = {id(n) for a in ast.walk(tree) if isinstance(a, ast.Assign)
                      and any(getattr(t, "id", "") in ("FORBIDDEN_ARGS", "FORBIDDEN_PROMPTS") for t in a.targets)
                      for n in ast.walk(a.value)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and node.value in ("--continue", "-c", "/low-priority", "/rate-limit-options"):
                    self.assertIn(id(node), guards, "%s: %r" % (name, node.value))

    def test_run_once_against_fake_process(self):
        claude, log, env = make_fake(self, [{"do": "limit", "reset": "ms", "after": 5, "type": "seven_day"}])
        res = claude_run.run_once(claude, "작업", "sonnet", "medium", env=env, session_id="11111111-2222-3333-4444-555555555555")
        record = runs(log)[0]
        self.assertEqual((res["returncode"], res["limited"], res["rate_limit"]["kind"]), (1, True, "weekly"))
        self.assertAlmostEqual(res["rate_limit"]["resets_at"], record["reset"] / 1000.0, places=3)
        self.assertEqual((record["session_id"], record["model"], record["effort"], res["session_id"]),
                         ("11111111-2222-3333-4444-555555555555", "sonnet", "medium", "11111111-2222-3333-4444-555555555555"))
        missing = claude_run.run_once(os.path.join(os.path.dirname(claude), "없음"), "작업", "sonnet", "medium",
                                      env=env, session_id="u")
        self.assertEqual((missing["returncode"], missing["limited"], missing["success"]), (None, False, False))
        self.assertIn("FileNotFoundError", missing["error"])


if __name__ == "__main__":
    unittest.main()
