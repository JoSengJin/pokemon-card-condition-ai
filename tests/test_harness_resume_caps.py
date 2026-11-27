"""2차 결함 G3·G8·G9·G10·G12·변이 N24·N37(가짜 claude = 실제 하위 프로세스, 모델 호출 없음).

G3 한 작업의 자동 재개(한도 뒤 재개·실행 중 사망 뒤 재개·복원 불가 뒤 새 세션)는 모두 합쳐 recovery.MAX_INTERRUPTS(2)회까지다. 넘으면 그 작업만 대기.
G8 세션 복원 불가는 stdout의 비어 있지 않은 줄이 그 result 하나뿐이고 종료 코드가 정확히 int 1일 때만(실환경 t4-bogus-resume.jsonl은 한 줄).
N37 복원 불가 뒤 새 세션 직전에도 정지 상태를 다시 본다(실패한 --resume 중에 건 정지 뒤에는 새 세션을 열지 않는다).
G9·N24 시각 미상 한도 횟수 파일이 깨졌거나 값이 이상하면 소진으로 본다(Claude만 멈추고 전체 정지가 아니다).
G12 프로세스가 총 시간 직전에 끝나도 출력을 다 읽을 시간(KILL_GRACE_S)을 준다(정상 출력을 timeout_total로 보지 않는다).
G10 비밀 가림: 이스케이프된 JSON 따옴표, Authorization Basic, URL 사용자 정보, 공백이 든 따옴표 값, PEM 블록, 쿠키 여러 값.
"""
import functools
import json
import os
import sys
import tempfile
import time
import unittest

from harness import claude_job, claude_run, evidence, opstate, ratelimit, states, supervisor
from tests.test_harness_resume_fixes import REAL_NO_SESSION, SID, found
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_supervisor_kit import Clock, llm_task, make_fake, runs

LATE = '''#!%s
import os, sys, time
if os.fork() == 0:  # 새 세션 손자가 stdout을 물려받아 claude가 끝난 뒤에 결과 줄을 낸다(출력 읽기가 총 시간 직후까지 이어진다)
    os.setsid()
    time.sleep(2.3)
    print('{"type":"result","subtype":"success","is_error":false}', flush=True)
    os._exit(0)
time.sleep(1.2)
'''


def stop_then_unrecoverable(root, argv, env):
    """주입 runner: --help에는 옵션을 돌려주고, --resume 실행이면 처리 도중 USER_STOPPED를 건 뒤 실환경 '없는 세션' 출력으로 실패한다."""
    if "--help" in argv:
        return 0, "--model --effort"
    if "--resume" not in argv:
        raise AssertionError("복원 불가 뒤 정지 중에 새 세션을 열었다")
    opstate.set_condition(root, opstate.USER_STOPPED, 2.0, "user", "재개 실행 중 정지")
    return 1, REAL_NO_SESSION.replace("{SID}", argv[argv.index("--resume") + 1]) + "\n"


class ResumeCapTest(unittest.TestCase):
    def test_all_automatic_resumes_of_a_task_share_the_two_resume_limit(self):
        root = tempfile.mkdtemp()
        steps = [{"do": "limit", "after": 1}, {"do": "raw", "line": REAL_NO_SESSION, "code": 1}] * 3 + [{"do": "success"}]
        claude, log, env = make_fake(self, steps)
        key = llm_task(root)
        with allow_resume(self, "misanalysis_general"):
            out = supervisor.run(root, claude, max_cycles=10, poll_s=2, env=env)
        got = runs(log)  # 처음 실행 + 한도 뒤 재개 1회 + 복원 불가 뒤 새 세션 1회 = 자동 재개 2회, 그 뒤 대기
        self.assertEqual([r["resume"] is None for r in got], [True, False, True])
        self.assertEqual(out["outcomes"], ["rate_limited", "rate_limited", "blocked"])
        with open(claude_job.paths(root, key)[0], encoding="utf-8") as handle:
            job = json.load(handle)
        self.assertEqual((job["status"], job["crash_resumes"]), ("blocked", 2))
        self.assertTrue(job["hold_reason"].startswith("too_many_interrupts"), job)
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.PENDING)

    def test_unrecoverable_needs_a_single_result_line_and_an_int_exit_code(self):
        exact = REAL_NO_SESSION.replace("{SID}", SID)
        self.assertTrue(claude_run.session_unrecoverable(found(exact), SID))
        init = json.dumps({"type": "system", "subtype": "init", "session_id": SID})
        other = json.dumps(dict(json.loads(exact), errors=["x"]))
        near = [dict(ratelimit.scan([init, exact], 1), returncode=1), dict(ratelimit.scan([other, exact], 1), returncode=1),
                dict(ratelimit.scan(["not json", exact], 1), returncode=1), dict(found(exact), returncode=True),
                dict(found(exact), returncode=1.0)]
        self.assertEqual([claude_run.session_unrecoverable(f, SID) for f in near], [False] * len(near))

    def test_stop_during_an_unrecoverable_resume_opens_no_new_session(self):
        root = tempfile.mkdtemp()
        llm_task(root)
        job = dict(claude_job.pick(root, 1.0), session_id=SID, status="rate_limited")
        with allow_resume(self, "misanalysis_general"):
            outcome = claude_job.execute(root, job, "claude", time.time, functools.partial(stop_then_unrecoverable, root))
        self.assertEqual(outcome["kind"], "halted")

    def test_broken_unknown_limit_counter_counts_as_exhausted_without_halting_everything(self):
        for broken in ("{not json", json.dumps({"attempts": -1}), json.dumps({"attempts": "1"}), json.dumps({"attempts": True})):
            root = tempfile.mkdtemp()
            llm_task(root, "a")
            os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
            with open(os.path.join(root, claude_job.UNKNOWN_LIMIT), "w", encoding="utf-8") as handle:
                handle.write(broken)
            claude, log, env = make_fake(self, [{"do": "limit", "reset": "none"}] * 3)
            clock = Clock(1_000_000.0)
            out = supervisor.run(root, claude_bin=claude, max_cycles=10, poll_s=10 ** 6, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
            self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT, broken)
            self.assertEqual(len(runs(log)), 1, broken)  # 다시 시도하지 않는다(소진)
            [info] = opstate.load(root)["conditions"].values()
            self.assertTrue(info["exhausted"], broken)

    def test_output_finishing_right_after_an_exit_near_the_total_limit_is_not_a_timeout(self):
        base = tempfile.mkdtemp()
        fake = os.path.join(base, "claude")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write(LATE % sys.executable)
        os.chmod(fake, 0o755)
        code, out, more = claude_run.default_runner([fake], dict(os.environ), idle_s=60, total_s=2.0)
        self.assertEqual((code, more["cause"]), (0, None))
        self.assertIn('"result"', out)

    def test_more_secret_forms_are_masked(self):
        cases = ['{"msg": "{\\"token\\": \\"SECRETVAL123\\"}"}', "Authorization: Basic SECRETVAL123==",
                 "fetch https://user:SECRETVAL123@example.com/x", '{"password": "abc SECRETVAL123"}',
                 "-----BEGIN PRIVATE KEY-----\nSECRETVAL123\nMORE\n-----END PRIVATE KEY-----", "Cookie: a=1; session=SECRETVAL123",
                 "x-api-key: SECRETVAL123", "set-cookie: sid=SECRETVAL123; Path=/"]
        for text in cases:
            self.assertNotIn("SECRETVAL", evidence.mask(text), text)
        self.assertIn("example.com/x", evidence.mask(cases[2]))  # 가림 밖의 내용은 남긴다


if __name__ == "__main__":
    unittest.main()
