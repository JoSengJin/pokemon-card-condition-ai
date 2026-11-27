""""중단" 원문 → 훅 → opstate USER_STOPPED → 실제 supervisor.run이 아무것도 시작하지 않음."""
import os
import pathlib
import tempfile
import unicodedata
import unittest

from harness import ledger, opstate, queue, supervisor
from tests.test_harness_gold_support import hook
from tests.test_harness_runner_kit import task


class GoldStopTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_stop_sets_user_stopped_and_supervisor_starts_nothing(self):
        control = tempfile.mkdtemp()
        for root in (control, self.root):
            queue.enqueue(root, task("py"), 1.0)
        reply = hook(self, self.root, "  \u3000중단\u3000 \n")  # 전각 공백도 앞뒤 공백이다
        self.assertIn("중단 접수: USER_STOPPED를 기록했다.", reply)
        state = opstate.load(self.root)
        self.assertEqual(opstate.effective(state), opstate.USER_STOPPED)
        self.assertEqual(state["conditions"][opstate.USER_STOPPED]["actor"], "user")
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])
        runs = {}
        for root in (control, self.root):
            out = supervisor.run(root, None, "tests.test_harness_executors:EXECUTORS", max_cycles=2, poll_s=0,
                                 sleep_fn=int)
            runs[root] = (out["state"], out["python_runs"] > 0)
        self.assertEqual(runs, {control: (opstate.RUNNING, True), self.root: (opstate.USER_STOPPED, False)})
        self.assertIn(opstate.USER_STOPPED, opstate.load(self.root)["conditions"])  # 자동 해제 없음
        self.assertIn("중단 접수", hook(self, self.root, "중단"))  # 두 번 눌러도 안전

    def test_only_the_exact_word_stops(self):
        for prompt in ("작업을 중단하지 마", "서버 중단 원인 알려줘", "stop", "중단\n그리고 계속", "중단해 주세요.."):  # 8자 초과
            self.assertEqual(hook(self, self.root, prompt), "", prompt)
        for prompt in ("중단.", "중단!", "중단?", "중단해", "중단 중단", "'중단'", "중단\u200b", unicodedata.normalize("NFD", "중단"),
                       "  중단해 주세요.  "):  # 마지막은 앞뒤 공백을 빼면 8자
            reply = hook(self, self.root, prompt)
            self.assertIn("정지 기록 안 함", reply, prompt)
            self.assertIn("정확히 '중단'", reply, prompt)
            self.assertNotIn("중단 접수", reply, prompt)
        self.assertEqual(os.listdir(self.root), [])
        self.assertIn("읽지 못함", hook(self, self.root, "중단", event="Stop"))
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RUNNING)

    def test_stop_stays_recorded_when_main_ledger_is_broken(self):
        pathlib.Path(self.root, "ledger.jsonl").write_text('{"broken": true}\n', encoding="utf-8")
        reply = hook(self, self.root, "중단")
        self.assertIn("중단 접수", reply)
        self.assertIn("기록 중 오류: LedgerError", reply)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.USER_STOPPED)

    def test_stop_is_not_claimed_when_not_recorded(self):
        os.makedirs(os.path.join(self.root, "supervisor"))
        path = pathlib.Path(self.root, opstate.OPSTATE)
        path.write_text("{깨진", encoding="utf-8")
        reply = hook(self, self.root, "중단")
        self.assertNotIn("중단 접수", reply)
        self.assertIn("확인하지 못함", reply)
        self.assertIn(opstate.INTEGRITY_HALT, reply)
        self.assertEqual(path.read_text(encoding="utf-8"), "{깨진")
        blocked = os.path.join(tempfile.mkdtemp(), "file")  # root가 폴더가 아니면 아무것도 쓸 수 없다
        pathlib.Path(blocked).write_text("x", encoding="utf-8")
        reply = hook(self, blocked, "중단")
        self.assertNotIn("중단 접수", reply)
        self.assertIn("확인하지 못함", reply)


if __name__ == "__main__":
    unittest.main()
