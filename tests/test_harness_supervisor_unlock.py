"""정지 해제(unlock): too_many_interrupts·holder_alive_without_lock을 사람 확인 뒤 푸는 함수, 장부 기록, 자동 호출 경로 없음."""
import ast
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from harness import lease, queue, recovery, unlock
from tests.test_harness_supervisor_kit import events
from tests.test_harness_support import RERUN_SAFE, BOOT, REPO, claim, dead_lease, make_contract


@mock.patch.object(recovery, "RERUN_SAFE_TYPES", RERUN_SAFE)  # 재실행 절차 시험: 등록 유형으로 본다
class UnlockTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.key = queue.enqueue(self.root, make_contract(), 1_000_000.0)
        self.dir = os.path.join(self.root, "tasks", self.key)
        patcher = mock.patch.object(lease, "boot_id", return_value=BOOT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_release_too_many_interrupts(self):
        dead_lease(self.root, self.key, 1_000_000.0, run_id="abc1")
        with open(os.path.join(self.dir, "lease.json")) as handle:
            record = dict(json.load(handle), interrupts=2)
        with open(os.path.join(self.dir, "lease.json"), "w") as handle:
            json.dump(record, handle)
        stopped = claim(self.root, self.key, os.getpid(), BOOT, 1_000_100.0)
        self.assertEqual((stopped["ok"], stopped["plan"]["reason"]), (False, "too_many_interrupts"))
        with self.assertRaises(ValueError):
            unlock.release_interrupts(self.root, self.key, "user", "확인", 1_000_200.0)  # confirm 없음
        done = unlock.release_interrupts(self.root, self.key, "user", "중단 원인 확인", 1_000_200.0, confirm=True)
        self.assertTrue(done["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "stopped.json")))
        with open(done["archived"]) as handle:
            kept = json.load(handle)
        self.assertEqual((kept["stopped"]["run_id"], kept["lease"]["interrupts"], kept["actor"]), ("abc1", 2, "user"))
        row = events(self.root, "unlock_too_many_interrupts")[0]
        self.assertEqual((row["ts"], row["data"]["actor"], row["data"]["reason"], row["data"]["run_id"]),
                         (1_000_200.0, "user", "중단 원인 확인", "abc1"))
        again = claim(self.root, self.key, os.getpid(), BOOT, 1_000_300.0)
        self.assertEqual((again["ok"], again["plan"]["action"], again["plan"]["interrupts"]), (True, "rerun", 1))
        lease.release(again["lease"], remove=True)

    def test_release_holder_alive_without_lock(self):
        live = subprocess.Popen(["sleep", "30"])
        self.addCleanup(live.wait)
        self.addCleanup(live.kill)
        dead_lease(self.root, self.key, 1_000_000.0, run_id="abc2", pid=live.pid)
        blocked = claim(self.root, self.key, os.getpid(), BOOT, 1_000_100.0)
        self.assertEqual(blocked["reason"], "holder_alive_without_lock")
        for actor in ("bot", "", None):
            with self.assertRaises(ValueError):
                unlock.release_holder(self.root, self.key, actor, "확인", 1_000_200.0, confirm=True)
        done = unlock.release_holder(self.root, self.key, "supervisor", "pid 재사용 확인", 1_000_200.0, confirm=True)
        self.assertTrue(done["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "lease.json")))
        row = events(self.root, "unlock_holder_alive")[0]["data"]
        self.assertEqual((row["actor"], row["holder"]["pid"], row["holder"]["run_id"]), ("supervisor", live.pid, "abc2"))
        again = claim(self.root, self.key, os.getpid(), BOOT, 1_000_300.0)
        self.assertEqual((again["ok"], again["plan"]["action"]), (True, "run"))
        lease.release(again["lease"], remove=True)

    def test_refusals_change_nothing(self):
        before = len(events(self.root))
        self.assertEqual(unlock.release_interrupts(self.root, self.key, "user", "x", 1.0, confirm=True)["reason"], "not_stopped")
        self.assertEqual(unlock.release_holder(self.root, self.key, "user", "x", 1.0, confirm=True)["reason"], "no_lease")
        dead_lease(self.root, self.key, 1_000_000.0, run_id="abc3")  # 죽은 주인: 해제할 필요 없음(claim이 인수)
        self.assertEqual(unlock.release_holder(self.root, self.key, "user", "x", 1.0, confirm=True)["reason"],
                         "holder_not_alive_without_lock:dead")
        held = lease.lock(os.path.join(self.dir, "lease.json"))  # 실제로 잠금을 쥔 실행 중 작업
        self.addCleanup(lease.release, held)
        with open(os.path.join(self.dir, "stopped.json"), "w") as handle:
            json.dump({"run_id": "abc3", "interrupts": 3}, handle)
        self.assertEqual(unlock.release_interrupts(self.root, self.key, "user", "x", 1.0, confirm=True)["reason"], "locked")
        self.assertEqual(unlock.release_holder(self.root, self.key, "user", "x", 1.0, confirm=True)["reason"], "locked")
        self.assertEqual(len(events(self.root)), before)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "stopped.json")))

    def test_release_interrupts_refuses_run_id_mismatch(self):
        dead_lease(self.root, self.key, 1_000_000.0, run_id="abc4")
        path = os.path.join(self.dir, "lease.json")
        with open(path) as handle:
            record = dict(json.load(handle), interrupts=3)
        with open(path, "w") as handle:
            json.dump(record, handle)
        with open(os.path.join(self.dir, "stopped.json"), "w") as handle:
            json.dump({"run_id": "other-run", "interrupts": 3}, handle)  # 정지 표식이 다른 실행의 것
        before = len(events(self.root))
        got = unlock.release_interrupts(self.root, self.key, "user", "확인", 1_000_200.0, confirm=True)
        self.assertEqual(got, {"ok": False, "reason": "not_too_many_interrupts"})
        with open(path) as handle:
            self.assertEqual(json.load(handle)["interrupts"], 3)  # 작업권 기록 그대로
        self.assertTrue(os.path.exists(os.path.join(self.dir, "stopped.json")))
        self.assertEqual(len(events(self.root)), before)

    def test_no_automatic_call_path(self):
        harness = os.path.join(REPO, "harness")
        for name in sorted(os.listdir(harness)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(harness, name), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
                   {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                   {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
            if name != "unlock.py":
                self.assertFalse(used & {"unlock", "release_interrupts", "release_holder"}, name)
            if name != "opstate.py":
                self.assertNotIn("clear_by_user", used, name)  # 사용자 해제 함수는 하네스 코드가 부르지 않는다


if __name__ == "__main__":
    unittest.main()
