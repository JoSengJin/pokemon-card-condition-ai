"""2단계 runner 시험(T2-main·nollm·transient·det·stop 등). 합성 작업이며 모델 성능·실제 ./experiment 근거가 아니다."""
import ast
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from harness import ledger, lease, queue, runner, states
from tests.test_harness_runner_kit import count, link_result, run, task, write_result
from tests.test_harness_support import BOOT, REPO, RUNNER_PATH, alive_with

T0 = 1_000_000.0


@unittest.skipUnless(sys.platform == "darwin", "runner는 실제 부팅 식별자(macOS kern.boottime)를 쓴다")
class RunnerTest(unittest.TestCase):
    def test_main_runs_python_tasks_and_leaves_llm_tasks_and_their_dependents_pending(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            a, b = queue.enqueue(root, task("A", n="10"), T0), queue.enqueue(root, task("B", n="20"), T0)
            llm = queue.enqueue(root, task("L", needs_llm=True), T0)
            dep = queue.enqueue(root, task("D", depends_on=[llm]), T0)
            dep2 = queue.enqueue(root, task("D2", depends_on=[dep]), T0)  # LLM 작업에 간접으로 의존
            self.assertIsNone(shutil.which("claude", path=RUNNER_PATH))  # runner 환경 PATH에 claude가 없다
            summary = run(self, root, marks)
            self.assertEqual((sorted(summary["done"]), summary["failed"], summary["stopped"]), (sorted([a, b]), [], {}))
            self.assertEqual((summary["untouched"]["llm"], summary["untouched"]["llm_dependents"]), ([llm], sorted([dep, dep2])))
            alive = alive_with()
            for key, want in ((a, "55"), (b, "210")):
                tdir = os.path.join(root, "tasks", key)
                self.assertEqual(states.classify(tdir, T0, alive), states.VERIFIED)  # 출력 manifest 해시 검증 통과
                self.assertEqual(pathlib.Path(tdir, "out", "result.txt").read_text(), want)
            for key, name in ((llm, "L"), (dep, "D"), (dep2, "D2")):
                self.assertEqual(states.classify(os.path.join(root, "tasks", key), T0, alive), states.PENDING)
                self.assertEqual(count(marks, name), 0)
                self.assertFalse(os.path.exists(os.path.join(root, "tasks", key, "lease.json")))
            path = os.path.join(root, "ledger.jsonl")
            events = [json.loads(line) for line in pathlib.Path(path).read_text().splitlines()]
            self.assertEqual(ledger.verify(path), [])
            self.assertEqual(sorted(e["data"]["task_key"] for e in events if e["event"] == "claimed"), sorted([a, b]))

    def test_runner_source_has_no_llm_or_network_imports_or_calls(self):
        src = pathlib.Path(REPO, "harness", "runner.py").read_text()
        tree, imported, called = ast.parse(src), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Attribute):
                called.add(node.attr)
        banned = {"subprocess", "socket", "ssl", "urllib", "http", "requests", "anthropic", "openai", "asyncio", "multiprocessing"}
        self.assertEqual(imported & banned, set())
        self.assertEqual(called & {"system", "popen", "Popen", "run", "execv", "execvp", "fork", "urlopen"}, set())
        self.assertNotIn("claude", src.lower())
        self.assertNotIn("anthropic", src.lower())

    def test_transient_errors_retry_twice_then_stop_and_later_drains_leave_it_alone(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            ok = queue.enqueue(root, task("OK", task_type="flaky", fails="2"), T0)  # 2번 실패 뒤 3번째 성공
            bad = queue.enqueue(root, task("BAD", task_type="flaky", fails="99"), T0)  # 계속 실패
            summary = run(self, root, marks)
            alive = alive_with()
            self.assertEqual(summary["done"], [ok])
            self.assertEqual(sorted(f for f in summary["failed"]), sorted([[ok, "transient"]] * 2 + [[bad, "transient"]] * 3))
            self.assertEqual(summary["stopped"], {bad: "needs_failure_policy"})
            self.assertEqual((count(marks, "OK"), count(marks, "BAD")), (3, 3))  # 최초 1회 + 재시도 2회
            self.assertEqual(states.classify(os.path.join(root, "tasks", ok), T0, alive), states.VERIFIED)
            self.assertEqual(states.classify(os.path.join(root, "tasks", bad), T0, alive), states.FAILED)
            size = os.path.getsize(os.path.join(root, "ledger.jsonl"))
            again = run(self, root, marks)
            self.assertEqual((again["executed"], again["stopped"]), (0, {bad: "needs_failure_policy"}))
            self.assertEqual((count(marks, "BAD"), os.path.getsize(os.path.join(root, "ledger.jsonl"))), (3, size))

    def test_code_error_is_not_retried_and_other_independent_tasks_continue(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            bug = queue.enqueue(root, task("BUG", task_type="buggy"), T0)
            fine = queue.enqueue(root, task("FINE"), T0)
            after = queue.enqueue(root, task("AFTER", depends_on=[bug]), T0)  # 실패한 작업에 의존: 건드리지 않는다
            summary = run(self, root, marks)
            self.assertEqual((summary["done"], summary["failed"], summary["stopped"]), ([fine], [[bug, "deterministic"]], {}))
            self.assertEqual((count(marks, "BUG"), count(marks, "AFTER")), (1, 0))
            self.assertEqual(summary["untouched"]["waiting_dependencies"], [after])
            self.assertEqual(run(self, root, marks)["stopped"], {bug: "needs_failure_policy"})
            self.assertEqual(count(marks, "BUG"), 1)

    def test_holder_alive_without_lock_stops_only_that_task(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            stuck, other = queue.enqueue(root, task("STUCK"), T0), queue.enqueue(root, task("OTHER"), T0)
            sleeper = subprocess.Popen(["sleep", "30"])  # 잠금 없이 살아 있는 주인
            self.addCleanup(sleeper.wait)
            self.addCleanup(sleeper.kill)
            handle = lease.lock(os.path.join(root, "tasks", stuck, "lease.json"))
            lease.stamp(handle, sleeper.pid, lease.boot_id(), T0, {"run_id": "abc123"})
            lease.release(handle)
            summary = run(self, root, marks)
            self.assertEqual((summary["done"], summary["stopped"]), ([other], {stuck: "holder_alive_without_lock"}))
            self.assertEqual((count(marks, "STUCK"), count(marks, "OTHER")), (0, 1))
            events = [json.loads(line)["event"] for line in pathlib.Path(root, "ledger.jsonl").read_text().splitlines()]
            self.assertEqual(events.count("holder_alive_without_lock"), 1)  # 같은 drain에서 다시 시도해 장부를 채우지 않는다

    def test_missing_executor_wrong_outputs_and_max_tasks(self):
        with tempfile.TemporaryDirectory() as root:
            noexec = queue.enqueue(root, task("NOEXEC", task_type="nobody"), T0)
            wrong = queue.enqueue(root, task("WRONG", task_type="wrong"), T0)
            fine = [queue.enqueue(root, task("F%d" % i, task_type="ok"), T0) for i in range(3)]

            executors = {"wrong": lambda t, o: write_result(t, o) and ["other.txt"], "ok": write_result}
            summary = runner.drain(root, executors, now_fn=lambda: T0, max_tasks=2, boot_id_fn=lambda: BOOT)
            self.assertEqual(summary["executed"], 2)  # max_tasks를 지킨다
            self.assertEqual(summary["untouched"]["no_executor"], [noexec])
            rest = runner.drain(root, executors, now_fn=lambda: T0, boot_id_fn=lambda: BOOT)
            self.assertEqual(sorted(summary["done"] + rest["done"] + [wrong]), sorted(fine + [wrong]))
            self.assertEqual([k for k, kind in rest["failed"]], [wrong] if wrong not in summary["failed"] else [])
            self.assertEqual(states.classify(os.path.join(root, "tasks", wrong), T0, alive_with()), states.FAILED)
            self.assertIn("OutputMismatch", states.failures(os.path.join(root, "tasks", wrong))[0]["error"])

    def test_unsafe_output_that_cannot_be_completed_becomes_a_deterministic_failure(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as elsewhere:
            key = queue.enqueue(root, task("LINK", task_type="link"), T0)

            summary = runner.drain(root, {"link": lambda t, o: link_result(o, elsewhere)}, now_fn=lambda: T0, boot_id_fn=lambda: BOOT)
            self.assertEqual((summary["done"], summary["failed"]), ([], [[key, "deterministic"]]))
            tdir = os.path.join(root, "tasks", key)
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.FAILED)
            self.assertFalse(os.path.exists(os.path.join(tdir, "lease.json")))  # 작업권을 쥔 채 남지 않았다
