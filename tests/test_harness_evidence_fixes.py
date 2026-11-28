"""검증 결함 F6·F7·F9·F10·F12(옵션 기록).

F6 새 세션(setsid)으로 떨어져 나간 손자가 claude의 stdout을 쥐고 있어도 default_runner는 총 시간 제한 안에 돌아오고 원인을 timeout_total로
   남기며, run_once는 그 실행을 성공으로 보지 않는다.
F7 비밀 가림: JSON 따옴표 값, 알려진 접두어(sk-·ghp_·github_pat_·AKIA·xox), Authorization: Bearer, 끝부분 경계에서 잘린 키.
F9 권한 거절 기록은 tool_name·tool_use_id·file_path만(쓰려던 본문 content는 남기지 않는다).
F12 증거의 CLI 옵션에 프롬프트(-p 본문)·--append-system-prompt·--settings 값이 없다.
F10 예산 멱등 키는 종류(kind)별이다: 같은 키라도 다른 종류의 차감은 빠지지 않는다.
"""
import os
import signal
import sys
import tempfile
import threading
import time
import unittest

from harness import budget, claude_run, evidence

T0 = 1_800_000_000.0
DETACHED = '''#!%s
import os, subprocess, sys, time
kid = subprocess.Popen([sys.executable, "-c", "import os, time; os.setsid(); time.sleep(20)"])  # stdout을 물려받은 새 세션 손자
open(sys.argv[1], "w").write(str(kid.pid))
time.sleep(0.5)
print('{"type":"result","subtype":"success","is_error":false}', flush=True)
'''


class EvidenceFixTest(unittest.TestCase):
    def test_f6_detached_grandchild_holding_stdout_does_not_outlive_the_total_limit(self):
        base = tempfile.mkdtemp()
        fake, pidfile = os.path.join(base, "claude"), os.path.join(base, "kid.pid")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write(DETACHED % sys.executable)
        os.chmod(fake, 0o755)
        box = {}
        worker = threading.Thread(target=lambda: box.update(got=claude_run.default_runner(
            [fake, pidfile], dict(os.environ), idle_s=60, total_s=2)), daemon=True)
        started = time.monotonic()
        worker.start()
        worker.join(10)
        try:
            self.assertFalse(worker.is_alive())  # 손자가 끝나는 20초까지 기다리지 않는다
            self.assertLess(time.monotonic() - started, 9)
            code, out, more = box["got"]
            self.assertEqual((code, more["cause"]), (0, "timeout_total"))
            found = claude_run.run_once(fake, "작업", "sonnet", "medium", runner=lambda argv, env: box["got"], session_id="s")
            self.assertEqual((found["success"], found["cause"]), (False, "timeout_total"))
        finally:
            with open(pidfile, encoding="utf-8") as handle:
                os.kill(int(handle.read()), signal.SIGKILL)

    def test_f7_secrets_in_quotes_known_prefixes_and_cut_boundaries_are_masked(self):
        cases = {'{"token": "ghp_abcdefghijklmnop1234"}': "ghp_abcdefghijklmnop1234",
                 "{'password': 'hunter2hunter2'}": "hunter2hunter2",
                 "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnop": "abcdefghijklmnop",
                 "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abcdefghij": "abcdefghij",
                 "aws_secret_access_key = AKIAABCDEFGHIJKLMNOP/xyz": "ABCDEFGHIJKLMNOP",
                 "use ghp_abcdefghijklmnopqrstuvwxyz0123 now": "abcdefghijklmnopqrstuvwxyz0123",
                 "slack xoxb-1234567890-abcdefghij": "abcdefghij",
                 "pat github_pat_11ABCDEFG0123456789_abcdefghijk": "abcdefghijk",
                 "Authorization: Bearer abc.def.ghi": "abc.def.ghi"}
        for text, secret in cases.items():
            self.assertNotIn(secret, evidence.mask(text), text)
        cut = "A" * 10 + "sk-ant-" + "K" * 1995  # 끝부분 2000자로 자르면 접두어가 잘려 나가는 위치
        self.assertNotIn("KKKKKKKK", evidence.mask(cut))
        self.assertLessEqual(len(evidence.mask(cut)), evidence.STDERR_TAIL)
        self.assertEqual(evidence.mask("plain log line"), "plain log line")

    def test_f9_f12_denials_and_options_keep_only_allowed_fields(self):
        found = {"returncode": 1, "result": {"subtype": "success", "is_error": False, "permission_denials": [
            {"tool_name": "Write", "tool_use_id": "t1",
             "tool_input": {"file_path": "/root/supervisor/opstate.json", "content": "GOLD_ANSWER: zone3=defect"}}]},
            "argv": ["claude", "-p", "SECRET PROMPT BODY", "--model", "sonnet", "--append-system-prompt", "HIDDEN SYSTEM TEXT",
                     "--settings", '{"env":{"ANTHROPIC_API_KEY":"sk-ant-zzz"}}', "--permission-mode", "dontAsk"],
            "stderr": "", "cause": "unknown"}
        rec = evidence.claude_record(found, "/cwd", 1.0, "unknown")
        self.assertEqual(rec["permission_denials"],
                         [{"tool_name": "Write", "tool_use_id": "t1", "file_path": "/root/supervisor/opstate.json"}])
        self.assertEqual(rec["options"], ["--model", "sonnet", "--permission-mode", "dontAsk"])
        text = repr(rec)
        for hidden in ("GOLD_ANSWER", "SECRET PROMPT", "HIDDEN SYSTEM", "sk-ant-zzz"):
            self.assertNotIn(hidden, text)

    def test_f10_idempotency_key_is_per_budget_kind(self):
        root = tempfile.mkdtemp()
        first = budget.charge(root, "experiment", 1, T0, key="task-1:run-1")
        other = budget.charge(root, "vision_zone", 3, T0, key="task-1:run-1")  # 같은 키, 다른 종류
        again = budget.charge(root, "vision_zone", 3, T0 + 1, key="task-1:run-1")
        self.assertEqual((first["ok"], other.get("already"), other["used"], again.get("already")), (True, None, 3, True))
        self.assertEqual(budget.usage(root, "vision_zone", other["period"]), 3)


if __name__ == "__main__":
    unittest.main()
