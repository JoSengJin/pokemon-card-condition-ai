"""B6-5·B6-6 사람 해제·재개: 근거 출력·1회용 확인 코드·confirm·사유가 모두 맞을 때만 이름 하나를 푼다. 문구만·지난 코드·다른 대상 코드로는 풀리지 않고
(중단 유지), 푼 뒤 실제 supervisor.run이 다시 작업을 시작한다. 합성 root·가짜 executor만 쓴다(실제 claude·훅 설치 없음)."""
import os
import pathlib
import tempfile
import unittest

from harness import control_release, ledger, opstate, queue, supervisor
from tests.test_harness_release_kit import cli, code_in, hook, stopped
from tests.test_harness_runner_kit import task
from tests.test_harness_supervisor_kit import events

SPEC = "tests.test_harness_executors:EXECUTORS"


class ControlReleaseTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        queue.enqueue(self.root, task("py"), 1.0)
        opstate.set_condition(self.root, opstate.USER_STOPPED, 1.0, "user", "RC 중단")

    def test_terminal_two_steps_release_once_and_supervisor_runs_again(self):
        out = supervisor.run(self.root, None, SPEC, max_cycles=1, poll_s=0, sleep_fn=int)
        self.assertEqual((out["state"], out["python_runs"]), (opstate.USER_STOPPED, 0))
        code, said, err = cli("--root", self.root, "--target", opstate.USER_STOPPED)
        self.assertEqual(code, 0, said + err)
        self.assertIn('"reason": "RC 중단"', said)  # 해제 전에 근거를 보인다
        self.assertIn("사용자 인증이 아니다", said)
        secret = code_in(err)
        self.assertNotIn(secret, said)
        self.assertTrue(stopped(self.root))  # 1단계만으로는 풀리지 않는다
        for args in (("--code", secret, "--reason", "확인"), ("--code", secret, "--confirm"),
                     ("--code", "%06d" % ((int(secret) + 1) % 10 ** 6), "--reason", "확인", "--confirm")):
            code, said, err = cli("--root", self.root, "--target", opstate.USER_STOPPED, *args)
            self.assertEqual(code, 1, args)
            self.assertIn("중단 상태 유지", said)
            self.assertTrue(stopped(self.root))
        code, said, err = cli("--root", self.root, "--target", opstate.USER_STOPPED, "--code", secret, "--reason", "원인 확인", "--confirm")
        self.assertEqual(code, 0, said + err)
        self.assertIn("해제 확인: USER_STOPPED", said)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RUNNING)
        row = [r for r in events(self.root, "opstate_transition") if r["data"]["op"] == "clear"][-1]["data"]
        self.assertEqual((row["condition"], row["actor"]), (opstate.USER_STOPPED, "user"))
        self.assertIn("원인 확인", row["reason"])
        self.assertIn("경로=terminal", row["reason"])
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])
        out = supervisor.run(self.root, None, SPEC, max_cycles=1, poll_s=0, sleep_fn=int)
        self.assertEqual((out["state"], out["python_runs"] > 0), (opstate.RUNNING, True))
        opstate.set_condition(self.root, opstate.USER_STOPPED, 2.0, "user", "다시 중단")
        code, said, _ = cli("--root", self.root, "--target", opstate.USER_STOPPED, "--code", secret, "--reason", "재생", "--confirm")
        self.assertEqual(code, 1)  # 쓴 코드 재생
        self.assertIn("발급된 확인 코드가 없다", said)
        self.assertTrue(stopped(self.root))

    def test_hook_phrase_alone_never_releases_and_code_is_user_only(self):
        code, out, err = hook(self.root, "재개 USER_STOPPED")
        self.assertEqual((code, out), (2, ""), err)  # 종료 코드 2: 프롬프트를 지우고 stderr는 사용자에게만(설치본 문자열 기준)
        secret = code_in(err)
        self.assertTrue(stopped(self.root))
        challenge = pathlib.Path(self.root, control_release.CHALLENGE).read_text(encoding="utf-8")
        self.assertNotIn(secret, challenge)  # 파일에는 sha256만
        for prompt in ("재개 USER_STOPPED", "재개", "재개 INTEGRITY_HALT %s" % secret, "재개 USER_STOPPED 12345"):
            hook(self.root, prompt)
            self.assertTrue(stopped(self.root), prompt)
        self.assertEqual(hook(self.root, "재개")[0], 0)  # 형식 안내만
        latest = code_in(hook(self.root, "재개 USER_STOPPED")[2])  # 새로 받으면 이전 코드는 무효
        if latest != secret:
            code, out, _ = hook(self.root, "재개 USER_STOPPED %s" % secret)
            self.assertIn("코드 불일치", out)
            self.assertTrue(stopped(self.root))
        code, out, err = hook(self.root, "  재개 USER_STOPPED %s \n" % latest)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("해제 확인: USER_STOPPED", out)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RUNNING)
        self.assertIn("경로=hook", events(self.root, "opstate_transition")[-1]["data"]["reason"])
        self.assertEqual(hook(self.root, "재개해")[:2], (0, ""))  # 대화 문장은 이 훅의 일이 아니다
        self.assertEqual(hook(self.root, "중단")[0], 0)  # 중단 훅은 그대로
        self.assertTrue(stopped(self.root))

    def test_wrong_tries_expiry_and_other_target_keep_the_stop(self):
        now = 10.0
        code, _, secret = control_release.request(self.root, opstate.USER_STOPPED, now, "test")
        wrong = "%06d" % ((int(secret) + 1) % 10 ** 6)
        for _ in range(control_release.MAX_TRIES):
            self.assertEqual(control_release.answer(self.root, opstate.USER_STOPPED, wrong, "x", now, "test", True)[0], 1)
        got = control_release.answer(self.root, opstate.USER_STOPPED, secret, "x", now, "test", True)
        self.assertEqual(got[0], 1)  # 세 번 틀리면 맞는 코드도 무효
        self.assertTrue(stopped(self.root))
        _, _, secret = control_release.request(self.root, opstate.USER_STOPPED, now, "test")
        got = control_release.answer(self.root, opstate.USER_STOPPED, secret, "x", now + control_release.TTL_S + 1, "test", True)
        self.assertEqual(got[0], 1)
        self.assertIn("만료", got[1])
        opstate.set_condition(self.root, opstate.BUDGET_EXCEEDED, now, "supervisor", "예산")
        _, _, secret = control_release.request(self.root, opstate.BUDGET_EXCEEDED, now, "test")
        got = control_release.answer(self.root, opstate.USER_STOPPED, secret, "x", now, "test", True)
        self.assertIn("다른 대상", got[1])
        self.assertEqual(set(opstate.load(self.root)["conditions"]), {opstate.USER_STOPPED, opstate.BUDGET_EXCEEDED})
        rejected = [r["data"]["why"] for r in events(self.root, "release_challenge") if r["data"]["op"] == "rejected"]
        self.assertEqual(len(rejected), control_release.MAX_TRIES + 3)
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
