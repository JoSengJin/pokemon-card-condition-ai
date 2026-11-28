"""B6-3 중단: 제어 진입점의 stop이 opstate 규칙대로 USER_STOPPED를 기록하고, 다시 읽어 확인한 사실만 말한다."""
import io
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from harness import control, ledger, opstate, queue, supervisor
from tests.test_harness_control_kit import cli, spawn
from tests.test_harness_runner_kit import task

class ControlStopTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        queue.enqueue(self.root, task("py"), 1.0)

    def test_stop_is_recorded_once_and_supervisor_starts_nothing(self):
        code, out = cli("stop", "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("중단 기록 확인: USER_STOPPED", out)
        self.assertIn("실행 중인 claude·executor는 끊지 않", out)
        first = opstate.load(self.root)["conditions"][opstate.USER_STOPPED]
        self.assertEqual(first["actor"], "control_cli")  # 훅("user")·Supervisor와 구분되는 기록용 이름
        code, again = cli("stop", "--root", self.root, "--reason", "두 번째")
        self.assertEqual(code, 0)
        self.assertIn("이미 중단 상태", again)
        self.assertEqual(opstate.load(self.root)["conditions"], {opstate.USER_STOPPED: first})  # since·사유를 덮지 않는다
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])
        out = supervisor.run(self.root, None, "tests.test_harness_executors:EXECUTORS", max_cycles=2, poll_s=0, sleep_fn=int)
        self.assertEqual((out["state"], out["python_runs"]), (opstate.USER_STOPPED, 0))
        code, shown = cli("status", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertIn("상태: 사용자 중단(USER_STOPPED)", shown)
        self.assertIn("<!doctype html>", cli("status", "--root", self.root, "--html")[1])

    def test_limit_auto_resume_never_lifts_a_user_stop(self):
        opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "한도", {"next_try_at": 2.0})
        self.assertEqual(cli("stop", "--root", self.root)[0], 0)
        out = supervisor.run(self.root, None, "tests.test_harness_executors:EXECUTORS", max_cycles=3, poll_s=0, sleep_fn=int)
        self.assertEqual((out["state"], out["python_runs"]), (opstate.USER_STOPPED, 0))
        self.assertIn(opstate.USER_STOPPED, opstate.load(self.root)["conditions"])
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_auto(self.root, opstate.USER_STOPPED, 3.0, "자동 재개")
        for word in ("resume", "release", "clear"):  # 해제 명령은 없다(B6-5 미구현)
            self.assertEqual(cli(word, "--root", self.root)[0], 2, word)
        self.assertIn(opstate.USER_STOPPED, opstate.load(self.root)["conditions"])

    def test_concurrent_stops_leave_one_condition_and_a_valid_ledger(self):
        procs = [spawn("stop", "--root", self.root) for _ in range(4)]
        for proc in procs:
            proc.communicate(timeout=60)
        self.assertEqual([p.returncode for p in procs], [0, 0, 0, 0])
        self.assertEqual(list(opstate.load(self.root)["conditions"]), [opstate.USER_STOPPED])
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])

    def test_failure_is_never_reported_as_stopped(self):
        sup = pathlib.Path(self.root, "supervisor")
        sup.mkdir()
        sup.joinpath("opstate.json").write_text("{깨진", encoding="utf-8")
        code, out = cli("stop", "--root", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("중단을 기록하지 못함", out)
        self.assertNotIn("중단 기록 확인", out)
        self.assertEqual(sup.joinpath("opstate.json").read_text(encoding="utf-8"), "{깨진")
        sup.joinpath("opstate.json").unlink()
        for fault in (mock.patch.object(opstate, "set_condition", side_effect=OSError("쓰기 거절")),
                      mock.patch.object(opstate, "set_condition", return_value={})):  # 성공처럼 돌아왔지만 안 남음: 다시 읽어야 안다
            printed = io.StringIO()
            with fault, redirect_stdout(printed):
                code = control.main(["stop", "--root", self.root])
            self.assertEqual(code, 1, printed.getvalue())
            self.assertNotIn("중단 기록 확인", printed.getvalue())

    def test_broken_main_ledger_still_stops_and_says_so(self):
        pathlib.Path(self.root, "ledger.jsonl").write_text('{"broken": true}\n', encoding="utf-8")
        code, out = cli("stop", "--root", self.root, "--reason", "")  # 빈 사유가 중단을 막지 않는다
        self.assertEqual(code, 0, out)
        self.assertIn("기록 중 오류: LedgerError", out)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.USER_STOPPED)

    def test_a_mistyped_root_is_refused_and_nothing_is_created(self):
        empty = tempfile.mkdtemp()
        for root in (empty, os.path.join(empty, "no-such")):
            for command in ("stop", "status"):
                code, out = cli(command, "--root", root)
                self.assertEqual(code, 1, out)
                self.assertIn("하네스 root가 아니", out)
                self.assertNotIn("중단 기록 확인", out)
        self.assertEqual(os.listdir(empty), [])


if __name__ == "__main__":
    unittest.main()
