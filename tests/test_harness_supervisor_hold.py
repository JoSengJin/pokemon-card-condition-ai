"""Claude 작업 칸의 사람 확인 대기(검증 지적 4·5·7·8): pid 기록이 job과 맞지 않으면 자동 재개 안 함, pid 대기의 부팅 ID 확인,
원인을 모르는 claude 실패는 결정적 FAILED가 아니라 사람 확인 대기, init이 알려준 세션 ID 반영, 8일 넘는 재개 시각은 미상+알림."""
import os
import tempfile
import time
import unittest

from harness import claude_job, lease, opstate, states, supervisor
from harness.jsonio import read_json, write_json
from tests.test_harness_supervisor_kit import Clock, events, llm_task, make_fake, runs


def _queue_state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class ClaudeHoldTest(unittest.TestCase):
    def test_pid_record_not_matching_job_waits_for_human(self):
        claude, log, env = make_fake(self, [{"do": "success"}] * 3)
        base = {"pid": 999999, "boot_id": lease.boot_id()}  # 죽은 pid: 예전 코드는 이것만 보고 --resume했다
        records = (dict(base, session_id="s-old", mode="new", run_token="t-new"),  # 이전 세션의 낡은 pid 파일
                   dict(base, session_id="s-new", mode="resume", run_token="t-new"),  # mode 불일치
                   dict(base, session_id="s-new", mode="new", run_token="t-old"),  # 같은 세션·mode의 이전 실행
                   base, None)  # session·mode 없는 기록, 기록 없음
        for record in records:
            root = tempfile.mkdtemp()
            key = llm_task(root)
            job = claude_job.pick(root, 1.0)
            # Supervisor가 작업 상태 파일에 새 세션을 적은 뒤 pid를 기록하기 전에 죽은 상태(claude가 떠 있을 수도 있다)
            jobfile, pidfile = claude_job.paths(root, key)
            write_json(jobfile,
                       dict(job, status="running", mode="new", session_id="s-new", run_token="t-new"))
            if record is not None:
                write_json(pidfile, record)
            self.assertIsNone(claude_job.pick(root, 2.0), record)
            out = supervisor.run(root, claude, max_cycles=3, poll_s=0, env=env)
            held = read_json(jobfile)
            self.assertEqual((held["status"], held["session_id"], out["claude_runs"]), ("blocked", "s-new", 0), record)
            self.assertEqual(_queue_state(root, key), states.PENDING)  # 큐 작업은 그대로(다시 고르지도 않는다)
            self.assertEqual([e["data"]["kind"] for e in events(root, path=opstate.NOTIFICATIONS)], ["claude_job_blocked"])
            self.assertEqual(len(events(root, "claude_job_picked")), 1)
        self.assertEqual(runs(log), [])

    def test_pid_wait_checks_boot_id(self):
        root = tempfile.mkdtemp()
        jobfile, pidfile = claude_job.paths(root, llm_task(root))
        job = claude_job.pick(root, 1.0)
        write_json(jobfile, dict(job, status="running", mode="new", session_id="s-1", run_token="t-1"))
        record = {"pid": os.getpid(), "boot_id": lease.boot_id(), "session_id": "s-1", "mode": "new", "run_token": "t-1"}
        write_json(pidfile, record)
        self.assertIsNone(claude_job.pick(root, 2.0))  # 같은 부팅에서 살아 있음: 겹쳐 실행하지 않고 기다린다
        write_json(pidfile, dict(record, boot_id="other-boot"))
        again = claude_job.pick(root, 3.0)  # 다른 부팅의 pid: 살아 있는 번호여도 그 claude가 아니다 → 이어간다
        self.assertEqual((again["status"], again["session_id"]), ("running", "s-1"))

    def test_unexplained_claude_failure_waits_for_human_not_failed(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "fail"}, {"do": "success"}])
        key = llm_task(root)
        out = supervisor.run(root, claude, max_cycles=3, poll_s=0, env=env)
        self.assertEqual((out["outcomes"], len(runs(log))), (["blocked"], 1))  # 자동 재시도 없음
        self.assertEqual((_queue_state(root, key), states.failures(os.path.join(root, "tasks", key))), (states.PENDING, []))
        self.assertEqual(read_json(claude_job.paths(root, key)[0])["status"], "blocked")
        self.assertEqual([e["data"]["kind"] for e in events(root, path=opstate.NOTIFICATIONS)], ["claude_job_blocked"])

    def test_session_id_from_init_is_followed(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "limit", "after": 1, "session": "init-told"}, {"do": "success"}])
        key = llm_task(root)
        supervisor.run(root, claude, max_cycles=4, poll_s=2, env=env)
        first, second = runs(log)
        self.assertNotEqual(first["session_id"], "init-told")
        self.assertEqual(second["resume"], "init-told")  # 요청한 ID가 아니라 init이 알려준 ID로 이어간다
        self.assertEqual(_queue_state(root, key), states.VERIFIED)

    def test_reset_more_than_8_days_ahead_is_unknown_and_notified(self):
        for ahead, far in ((9 * 86400, True), (7 * 86400, False)):
            root = tempfile.mkdtemp()
            claude, log, env = make_fake(self, [{"do": "limit", "after": ahead}])
            llm_task(root)
            clock = Clock(time.time())
            supervisor.run(root, claude, max_cycles=1, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
            info = opstate.load(root)["conditions"][opstate.RATE_LIMITED_SHORT]
            want = clock.now() + claude_job.UNKNOWN_BACKOFF_S[0] if far else info["resets_at"]
            self.assertEqual((info["next_try_at"], info["unknown_attempts"]), (want, 0), ahead)
            self.assertAlmostEqual(info["resets_at"], runs(log)[0]["reset"], places=3)  # 받은 값은 기록해 둔다
            notes = [e["data"]["kind"] for e in events(root, path=opstate.NOTIFICATIONS)]
            self.assertEqual(notes, ["rate_limit_reset_too_far"] if far else [], ahead)


if __name__ == "__main__":
    unittest.main()
