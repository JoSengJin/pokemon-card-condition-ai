"""B6-5 해제 대상 규칙: 이름 하나만(DONE·awaiting·blocked·"전부" 없음), 손상 상태는 풀지 않음, 소진 한도 해제 뒤 횟수 유지(결정 4), 작업 정지(unlock)
해제는 실행 중 작업을 거절, 같은 코드의 동시 2단계는 한 번만 푼다."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from harness import claude_job, control_release, ledger, lease, opstate, queue, recovery
from tests.test_harness_release_kit import cli, stopped
from tests.test_harness_runner_kit import task
from tests.test_harness_status_collect import tree
from tests.test_harness_supervisor_kit import events
from tests.test_harness_support import BOOT, REPO, RERUN_SAFE, claim, dead_lease


class ReleaseTargetTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        queue.enqueue(self.root, task("py"), 1.0)
        opstate.set_condition(self.root, opstate.USER_STOPPED, 1.0, "user", "RC 중단")


    def test_only_one_named_target_and_no_code_for_non_targets(self):
        for target in ("FOO", opstate.DONE, "awaiting:" + "0" * 64, "all", "", opstate.RATE_LIMITED_SHORT, "interrupts:bad"):
            code, text, secret = control_release.request(self.root, target, 1.0, "test")
            self.assertEqual((code, secret), (1, None), target)
        self.assertIn("수동 절차", control_release.request(self.root, "awaiting:x", 1.0, "test")[1])
        self.assertFalse(os.path.exists(os.path.join(self.root, control_release.CHALLENGE)))
        code, said, err = cli("--root", tempfile.mkdtemp(), "--target", opstate.USER_STOPPED)
        self.assertEqual(code, 1)
        self.assertIn("하네스 root가 아니", said)
        self.assertEqual(cli("--root", self.root)[0], 2)  # 대상 없음: 전부 해제는 없다
        broken = pathlib.Path(self.root, opstate.OPSTATE)
        broken.write_text("{깨진", encoding="utf-8")
        before = tree(self.root)
        code, text, secret = control_release.request(self.root, opstate.INTEGRITY_HALT, 1.0, "test")
        self.assertEqual((code, secret), (1, None))
        self.assertIn("손상", text)
        self.assertEqual(tree(self.root), before)  # 손상 파일을 덮지 않고 코드도 만들지 않는다

    def test_exhausted_limit_release_reports_and_keeps_the_counter(self):
        opstate.set_condition(self.root, opstate.RATE_LIMITED_UNKNOWN, 5.0, "supervisor", "한도 3회 소진",
                              {"next_try_at": None, "exhausted": True, "unknown_attempts": 3})
        pathlib.Path(self.root, claude_job.UNKNOWN_LIMIT).write_text('{"attempts": 3}', encoding="utf-8")
        code, text, secret = control_release.request(self.root, opstate.RATE_LIMITED_UNKNOWN, 6.0, "test")
        self.assertEqual(code, 0)
        self.assertIn('"exhausted": true', text)
        self.assertIn("자동 재개 대상", text)
        code, text = control_release.answer(self.root, opstate.RATE_LIMITED_UNKNOWN, secret, "한도 확인", 7.0, "test", True)
        self.assertEqual(code, 0, text)
        self.assertIn("3/3", text)
        self.assertEqual(json.loads(pathlib.Path(self.root, claude_job.UNKNOWN_LIMIT).read_text()), {"attempts": 3})  # 결정 4
        self.assertEqual(list(opstate.load(self.root)["conditions"]), [opstate.USER_STOPPED])  # 다른 조건은 그대로

    @mock.patch.object(recovery, "RERUN_SAFE_TYPES", RERUN_SAFE)
    def test_interrupt_stop_release_refuses_a_running_task(self):
        with mock.patch.object(lease, "boot_id", return_value=BOOT):
            key = queue.enqueue(self.root, task("int"), 1_000_000.0)
            folder = os.path.join(self.root, "tasks", key)
            dead_lease(self.root, key, 1_000_000.0, run_id="r1")
            path = os.path.join(folder, "lease.json")
            pathlib.Path(path).write_text(json.dumps(dict(json.loads(pathlib.Path(path).read_text()), interrupts=2)))
            self.assertEqual(claim(self.root, key, os.getpid(), BOOT, 1_000_100.0)["plan"]["reason"], "too_many_interrupts")
            target = "interrupts:" + key
            _, _, secret = control_release.request(self.root, target, 1_000_200.0, "test")
            held = lease.lock(path)
            got = control_release.answer(self.root, target, secret, "확인", 1_000_200.0, "test", True)
            lease.release(held)
            self.assertEqual(got[0], 1)
            self.assertIn("locked", got[1])
            self.assertTrue(os.path.exists(os.path.join(folder, "stopped.json")))
            _, _, secret = control_release.request(self.root, target, 1_000_300.0, "test")
            got = control_release.answer(self.root, target, secret, "원인 확인", 1_000_300.0, "test", True)
            self.assertEqual(got[0], 0, got[1])
            self.assertFalse(os.path.exists(os.path.join(folder, "stopped.json")))
            self.assertEqual(events(self.root, "unlock_too_many_interrupts")[0]["data"]["actor"], "user")
            self.assertTrue(stopped(self.root))  # 작업 정지만 풀었다: 운영 중단은 그대로

    def test_concurrent_answers_with_one_code_release_once(self):
        _, _, secret = control_release.request(self.root, opstate.USER_STOPPED, time.time(), "test")  # 하위 프로세스는 실제 시각으로 대조한다
        procs = [subprocess.Popen([sys.executable, "-m", "harness.control_release", "--root", self.root, "--target",
                                   opstate.USER_STOPPED, "--code", secret, "--reason", "동시", "--confirm"], cwd=REPO,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        codes = sorted(p.wait(timeout=120) for p in procs)
        for proc in procs:
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(codes, [0, 1, 1, 1])
        clears = [r for r in events(self.root, "opstate_transition") if r["data"]["op"] == "clear"]
        self.assertEqual(len(clears), 1)
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
