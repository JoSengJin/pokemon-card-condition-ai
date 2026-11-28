"""Supervisor 부가 계약: route 결정 장부 기록(T7 통과 주장 없음), root당 하나만 실행, launchd 템플릿(설치하지 않음)."""
import fcntl
import os
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

from harness import queue, states, supervisor
from tests.test_harness_runner_kit import WRAPPED_RUNNER, task
from tests.test_harness_supervisor_kit import REPO, SUPERVISOR, events, llm_task, make_fake, runs

TEMPLATE = os.path.join(REPO, "harness", "launchd", "harness-supervisor.plist.template")


class SupervisorContractTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_route_decision_recorded_without_claiming_t7(self):
        claude, log, env = make_fake(self, [{"do": "success"}, {"do": "success"}])
        llm_task(self.root, "a")
        llm_task(self.root, "b", task_type="repeated_failure_analysis")  # A 묶음의 opus·high 유형(B 묶음 label_disagreement는 실행 안 함)
        supervisor.run(self.root, claude, max_cycles=3, poll_s=0.01, env=env)
        rows = [e["data"] for e in events(self.root, "route_decision")]
        self.assertEqual(sorted((r["task_type"], r["requested"]["model"], r["requested"]["effort"]) for r in rows),
                         [("misanalysis_general", "sonnet", "medium"), ("repeated_failure_analysis", "opus", "high")])  # A 묶음 유형
        self.assertEqual(sorted((r["model"], r["effort"]) for r in runs(log)), [("opus", "high"), ("sonnet", "medium")])
        for row in rows:
            self.assertEqual((row["policy"], row["applied"]["verified"], row["applied"]["effort"]), ("routing-policy-v1", False, None))
            self.assertEqual(row["applied"]["source"], "stream-json init")
            joined = " ".join(row["limitations"])
            for needle in ("actual_application_unverified", "t7_not_claimed", "observed_effort_unavailable"):
                self.assertIn(needle, joined)
            self.assertEqual(row["tokens"], {"input_tokens": 1, "output_tokens": 2})
        self.assertEqual(len(runs(log, "help")), 2)  # 지원 확인은 가짜 claude의 --help로만(모델 호출 없음)

    def test_one_supervisor_per_root(self):
        os.makedirs(os.path.join(self.root, "supervisor"))
        with open(os.path.join(self.root, "supervisor", "supervisor.lock"), "a") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            self.assertEqual(supervisor.run(self.root, max_cycles=1), {"already_running": True})
            done = subprocess.run(SUPERVISOR + ["--root", self.root, "--max-cycles", "1"], cwd=REPO,
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 4)
        self.assertEqual(supervisor.run(self.root, max_cycles=1, poll_s=0)["cycles"], 1)
        with self.assertRaises(ValueError):
            supervisor._args(["--root", self.root, "--continue", "x"])

    def test_relative_root_is_made_absolute(self):
        base = tempfile.mkdtemp()
        key = queue.enqueue(os.path.join(base, "rel-root"), task("p"), 1.0)
        here = os.getcwd()
        os.chdir(base)  # runner는 cwd=REPO에서 돈다: 상대 경로를 그대로 넘기면 다른 폴더를 본다
        self.addCleanup(os.chdir, here)
        with mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": tempfile.mkdtemp()}), \
                mock.patch.object(supervisor, "RUNNER", WRAPPED_RUNNER):
            out = supervisor.run("rel-root", executors="tests.test_harness_executors:EXECUTORS", max_cycles=1, poll_s=0)
        task_dir = os.path.join(base, "rel-root", "tasks", key)
        self.assertEqual((out["python_runs"] >= 1, states.state_of(states.facts(task_dir), False)), (True, states.VERIFIED))

    def test_launchd_template_is_only_a_template(self):
        with open(TEMPLATE, encoding="utf-8") as handle:
            text = handle.read()
        for name in ("__LABEL__", "__PYTHON__", "__REPO__", "__ROOT__", "__CLAUDE_BIN__", "__EXECUTORS__", "__LOG_DIR__"):
            text = text.replace(name, "/x/" + name.strip("_").lower())
        plist = plistlib.loads(text.encode("utf-8"))
        self.assertEqual(plist["ProgramArguments"][1:3], ["-m", "harness.supervisor"])
        self.assertTrue(plist["KeepAlive"] and plist["RunAtLoad"])
        self.assertNotIn("--continue", plist["ProgramArguments"])
        self.assertEqual(supervisor._args(plist["ProgramArguments"][3:])["root"], "/x/root")


if __name__ == "__main__":
    unittest.main()
