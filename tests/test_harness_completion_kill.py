"""2단계 완료 표시와 kill 주입(Python 작업): 완료 표시 직후·done.json 직후·장부 기록 직전·직후에 runner를 kill -9 하고 다시 돌려도
executor를 다시 부르지 않고(반영만), 완료 반영은 한 번뿐이다. 산출물만 있고 완료 표시가 없으면 완료가 아니다."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from harness import queue, runner, states
from tests import test_harness_executors as executors
from tests.test_harness_runner_kit import count, task
from tests.test_harness_support import REPO
from tests.test_harness_supervisor_kit import events

KILL_AT = r'''
import os, sys
from harness import ledger, queue, runner
from tests import test_harness_executors as ex
root, point = sys.argv[1:3]
real_runner_write, real_queue_write, real_append = runner.write_json, queue.write_json, ledger.append
def die():
    os.kill(os.getpid(), 9)
def runner_write(path, obj):
    real_runner_write(path, obj)
    if point == "marker" and path.endswith("complete.json"):
        die()
def queue_write(path, obj):
    real_queue_write(path, obj)
    if point == "done" and path.endswith("done.json"):
        die()
def append(path, ts, event, data):
    if point == "ledger_before" and event == "completed":
        die()
    entry = real_append(path, ts, event, data)
    if point == "ledger_after" and event == "completed":
        die()
    return entry
runner.write_json, queue.write_json, ledger.append = runner_write, queue_write, append
runner.drain(root, ex.EXECUTORS, max_tasks=1)
'''


def crash_then_recover(case, point):
    """작업 1개를 point에서 kill -9 한 뒤 같은 root에서 runner를 다시 돌린다. (root, key, 표식 폴더, 두 번째 요약, kill 직후 done.json)."""
    root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
    key = queue.enqueue(root, task("k"), 1.0)
    env = dict(os.environ, HARNESS_MARK_DIR=marks, PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-c", KILL_AT, root, point], cwd=REPO, env=env, check=False, timeout=60)
    case.assertEqual(done.returncode, -9, point)
    path = os.path.join(root, "tasks", key, "done.json")
    before = pathlib.Path(path).read_text(encoding="utf-8") if os.path.exists(path) else None
    with mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks}):
        summary = runner.drain(root, executors.EXECUTORS)
    return root, key, marks, summary, before


class CompletionKillTest(unittest.TestCase):
    def test_kill_right_after_the_completion_marker_is_adopted_without_rerunning(self):
        root, key, marks, summary, before = crash_then_recover(self, "marker")
        self.assertIsNone(before)
        self.assertEqual((count(marks, "k"), summary["done"], summary["executed"]), (1, [key], 1))  # executor는 1회뿐
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.VERIFIED)
        self.assertEqual([e["event"] for e in events(root) if e["event"] in ("completion_adopted", "completed")],
                         ["completion_adopted", "completed"])

    def test_kill_after_done_record_or_around_the_ledger_line_is_never_completed_twice(self):
        for point, completed in (("done", 0), ("ledger_before", 0), ("ledger_after", 1)):
            root, key, marks, summary, before = crash_then_recover(self, point)
            path = os.path.join(root, "tasks", key, "done.json")
            self.assertEqual((count(marks, "k"), summary["executed"]), (1, 0), point)  # 다시 실행·반영하지 않는다
            self.assertEqual(pathlib.Path(path).read_text(encoding="utf-8"), before, point)  # done.json을 다시 쓰지 않았다
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.VERIFIED)
            # 장부 줄은 상태 변경 뒤에 쓰므로 done.json 직후 죽으면 completed 줄이 빠진다(상태 파일이 정본, queue.py 문서)
            self.assertEqual(len(events(root, "completed")), completed, point)

    def test_outputs_without_marker_are_not_complete_and_marker_must_match(self):
        root = tempfile.mkdtemp()
        key = queue.enqueue(root, task("m"), 1.0)
        res = queue.claim(root, key, os.getpid(), runner.lease.boot_id(), 2.0)
        out = os.path.join(root, "tasks", key, "out")
        os.makedirs(out)
        with open(os.path.join(out, "result.txt"), "w") as handle:
            handle.write("55")
        with self.assertRaises(queue.QueueError):  # 산출물 존재만으로는 완료가 아니다
            queue.complete(root, key, res["run_id"], res["lease"], 3.0)
        with open(os.path.join(root, "tasks", key, "complete.json"), "w") as handle:
            json.dump({"task_key": key, "outputs": {"result.txt": "0" * 64}}, handle)  # 해시가 다른 표시
        self.assertEqual(states.facts(os.path.join(root, "tasks", key))["completion"], "bad")
        with self.assertRaises(queue.QueueError):
            queue.complete(root, key, res["run_id"], res["lease"], 3.0)
        runner.lease.release(res["lease"], remove=True)
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.PENDING)


if __name__ == "__main__":
    unittest.main()
