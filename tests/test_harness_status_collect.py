"""B6-1 상태 수집(읽기 전용): 합성 root의 상태·작업·Claude 작업 칸·예산·장부를 모으고, 어떤 파일도 바꾸지 않는다."""
import fcntl
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

from harness import budget, opstate, queue, status, supervisor
from harness.jsonio import write_json
from tests.test_harness_support import BOOT, REPO, claim, dead_lease, finish, make_contract

NOW = 1_800_000_000.0


def tree(root):
    """{상대 경로: (종류, mtime_ns, sha256)}. 폴더 포함(빈 파일·폴더 생성도 잡는다)."""
    found = {}
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(base, name)
            sha = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() if os.path.isfile(path) else None
            found[os.path.relpath(path, root)] = (name in dirs, os.stat(path).st_mtime_ns, sha)
    return found


class StatusCollectTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_collect_reports_states_jobs_budget_and_notifications(self):
        done, _ = finish(self.root, make_contract("d"), NOW)
        queue.enqueue(self.root, make_contract("p"), NOW)
        halted = queue.enqueue(self.root, make_contract("s"), NOW)
        waiting = queue.enqueue(self.root, make_contract("w"), NOW)
        dead_lease(self.root, halted, NOW)
        write_json(os.path.join(self.root, "tasks", halted, "stopped.json"), {"run_id": "r-dead", "interrupts": 3})
        write_json(os.path.join(self.root, "tasks", waiting, "awaiting.json"), {"reason": "interrupted", "outcome": "partial"})
        jobs = os.path.join(self.root, "supervisor", "claude")
        write_json(os.path.join(jobs, "a" * 64 + ".json"), {"status": "blocked", "hold_reason": "claim_refused: x",
                                                           "crash_resumes": 2})
        write_json(os.path.join(jobs, "b" * 64 + ".json"), {"status": "done"})
        pathlib.Path(jobs, "c" * 64 + ".json").write_text("{깨진", encoding="utf-8")
        write_json(os.path.join(self.root, "supervisor", "claude_unknown_limit.json"), {"attempts": 3})
        budget.charge(self.root, "experiment", 2, NOW)
        for n in range(7):
            opstate.notify(self.root, NOW + n, "kind%d" % n, "알림 %d" % n)
        opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, NOW, "supervisor", "한도", {"next_try_at": NOW + 60})
        opstate.set_condition(self.root, opstate.USER_STOPPED, NOW, "user", "중단")

        got = status.collect(self.root, NOW + 10)

        self.assertEqual((got["state"], got["unreadable"], sorted(got["conditions"])),
                         ("USER_STOPPED", False, ["RATE_LIMITED_SHORT", "USER_STOPPED"]))
        self.assertEqual(got["tasks"]["counts"], {"VERIFIED": 1, "PENDING": 2, "INTERRUPTED": 1})
        self.assertEqual([t["task_key"] for t in got["tasks"]["stopped"]], [halted])
        self.assertEqual([(t["task_key"], t["detail"]["reason"]) for t in got["tasks"]["awaiting"]], [(waiting, "interrupted")])
        self.assertEqual([(j["task_key"], j["status"], j["hold_reason"], j["crash_resumes"]) for j in got["claude_jobs"]],
                         [("a" * 64, "blocked", "claim_refused: x", 2), ("c" * 64, "unreadable", None, None)])
        self.assertEqual(got["unknown_limit"], {"attempts": 3, "max": 3})
        self.assertEqual((got["budget"]["experiment"]["used"], got["budget"]["experiment"]["limit"],
                          got["budget"]["vision_zone"]["used"]), (2, 20, 0))
        self.assertEqual(got["ledgers"], {"ledger": 0, "notifications": 0})
        self.assertEqual([n["message"] for n in got["notifications"]], ["알림 4", "알림 5", "알림 6"])
        self.assertFalse(got["supervisor_running"])
        self.assertNotIn(done, [t["task_key"] for t in got["tasks"]["awaiting"]])

    def test_collect_writes_nothing_even_for_corrupt_or_missing_parts(self):
        key, _ = finish(self.root, make_contract("c"), NOW)
        pathlib.Path(self.root, "tasks", key, "out", "result.txt").write_text("변조", encoding="utf-8")  # 복구 가능한 CORRUPT
        os.makedirs(os.path.join(self.root, "supervisor"), exist_ok=True)
        before = tree(self.root)
        got = status.collect(self.root, NOW)
        self.assertEqual(got["tasks"]["counts"], {"CORRUPT": 1})  # 되살리지 않고 보고만
        self.assertEqual((got["state"], got["supervisor_running"], got["notifications"]), ("RUNNING", False, []))
        self.assertEqual(tree(self.root), before)  # supervisor.lock·알림 파일도 만들지 않는다
        running = claim(self.root, queue.enqueue(self.root, make_contract("r"), NOW), os.getpid(), BOOT, NOW)
        self.assertTrue(running["ok"])
        before = tree(self.root)
        status.collect(self.root, NOW)
        self.assertEqual(tree(self.root), before)

    def test_damage_is_reported_not_hidden_and_does_not_break_the_summary(self):
        queue.enqueue(self.root, make_contract(), NOW)
        sup = pathlib.Path(self.root, "supervisor")
        sup.mkdir()
        sup.joinpath("opstate.json").write_text("{깨진", encoding="utf-8")
        sup.joinpath("budget.jsonl").write_text("깨진 줄\n", encoding="utf-8")
        sup.joinpath("claude_unknown_limit.json").write_text("{", encoding="utf-8")
        sup.joinpath("notifications.jsonl").write_text("깨진 줄\n", encoding="utf-8")
        pathlib.Path(self.root, "ledger.jsonl").write_text('{"x": 1}\n', encoding="utf-8")
        got = status.collect(self.root, NOW)
        self.assertEqual((got["state"], got["unreadable"]), ("INTEGRITY_HALT", True))
        self.assertIn("error", got["budget"]["experiment"])
        self.assertIn("error", got["unknown_limit"])
        self.assertEqual(got["ledgers"], {"ledger": 1, "notifications": 1})
        sup.joinpath("claude_unknown_limit.json").write_text('{"attempts": true}', encoding="utf-8")
        self.assertIn("error", status.collect(self.root, NOW)["unknown_limit"])  # 이상한 값을 1회로 읽지 않는다
        sup.joinpath("opstate.json").unlink()
        sup.joinpath("opstate.json").mkdir()  # 읽을 수 없는 자리: 정상(RUNNING)으로 읽지 않는다
        got = status.collect(self.root, NOW)
        self.assertEqual((got["state"], got["unreadable"]), ("INTEGRITY_HALT", True))

    def test_lock_probe_sees_a_real_supervisor_and_releases_the_lock(self):
        opstate.set_condition(self.root, opstate.USER_STOPPED, NOW, "user", "아무것도 시작하지 않게")
        proc = subprocess.Popen([sys.executable, "-m", "harness.supervisor", "--root", self.root, "--poll", "0.2"], cwd=REPO,
                                stdout=subprocess.DEVNULL, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        time.sleep(1.0)  # 시작 전에 probe가 잠금 시도와 겹치지 않게
        deadline = time.time() + 30
        while not status.supervisor_running(self.root) and time.time() < deadline:
            time.sleep(0.1)
        self.assertIs(status.collect(self.root, NOW)["supervisor_running"], True)
        self.assertIsNone(proc.poll())
        proc.kill()
        proc.wait()
        self.assertIs(status.supervisor_running(self.root), False)
        self.assertNotIn("already_running", supervisor.run(self.root, max_cycles=1, sleep_fn=int))  # 조회가 잠금을 남기지 않았다
        with open(os.path.join(self.root, "supervisor", "supervisor.lock")) as other:  # 다른 조회가 동시에 보는 중
            fcntl.flock(other.fileno(), fcntl.LOCK_SH)
            self.assertIs(status.supervisor_running(self.root), False)  # 조회끼리는 서로를 Supervisor로 보지 않는다

    def test_only_a_real_harness_root_counts(self):
        self.assertFalse(status.is_harness_root(self.root))  # 빈 폴더
        self.assertFalse(status.is_harness_root(os.path.join(self.root, "no-such")))
        queue.enqueue(self.root, make_contract(), NOW)
        self.assertTrue(status.is_harness_root(self.root))


if __name__ == "__main__":
    unittest.main()
