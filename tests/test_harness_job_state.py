"""3차 결함 H6·H8·변이 S30: 자동 재개 근거(작업별 상태 파일·복원 불가 판정)는 형식이 다르면 열지 않는 쪽(fail-closed)으로 읽는다.

- H6 작업 상태 파일(supervisor/claude/<task_key>.json)이 있는데 JSON이 깨졌거나 dict가 아니거나 모르는 status면 새 작업으로 보지 않고 그 작업만
  대기(blocked, hold_reason job_state_invalid) + 알림 한 번. 독립 작업은 계속한다.
- S30 crash_resumes(자동 재개 합계)가 없음·null·정수 아님(bool 포함)·음수면 상한에 닿은 것으로 본다(claude를 부르지 않고 대기).
- H8 복원 불가 판정은 결과 이벤트의 session_id가 재개하려던 ID와 같을 때만 True(실환경 t4-bogus-resume.jsonl도 같다).
- 4차 결함 I6: status가 KNOWN 안이어도 내용이 모순이면 같은 job_state_invalid 대기다. 큐 작업이 PENDING인데 status가 done·failed·stale
  (정상 흐름에서는 큐가 VERIFIED·FAILED이거나 PENDING이 아닐 때만 쓴다), status new인데 crash_resumes가 정수 0이 아니거나 session_id가 있음
  (pick이 쓰는 new는 0·null뿐). 사람 해제는 그 작업의 상태 파일 삭제 한 가지뿐이다(지우면 새 작업으로 다시 고른다).
"""
import json
import os
import tempfile
import time
import unittest

from harness import claude_job, claude_run, opstate, recovery, states, supervisor
from harness.jsonio import write_json
from tests.test_harness_resume_fixes import REAL_NO_SESSION, found
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_supervisor_kit import events, llm_task, make_fake, runs

SID = "8c1fcaa7-3a7c-4d12-b546-2300ee06e3e0"  # 실환경 t4와 같은 모양(16진 글자 포함)


def no_claude(argv, env):
    """주입 runner: claude를 부르면 시험 실패."""
    raise AssertionError("상한에 닿은 작업에서 claude를 불렀다: %r" % (argv,))


class JobStateTest(unittest.TestCase):
    def test_invalid_job_state_file_holds_only_that_task_and_notifies_once(self):
        for text in ("[]", '"x"', "{not json", json.dumps({"task_key": "?", "status": "Blocked", "crash_resumes": 2}),
                     json.dumps({"task_key": "?", "crash_resumes": 0})):
            root = tempfile.mkdtemp()
            bad, good = llm_task(root, "a"), llm_task(root, "b")
            path = claude_job.paths(root, bad)[0]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            claude, log, env = make_fake(self, [{"do": "success"}] * 3)
            for _ in range(2):  # 두 번 돌려도 알림은 한 번, 대기 작업은 다시 열지 않는다
                out = supervisor.run(root, claude_bin=claude, max_cycles=4, poll_s=0, env=env)
            self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT, text)
            self.assertEqual(len(runs(log)), 1, text)  # 독립 작업 b만 실행
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", good)), False), states.VERIFIED, text)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", bad)), False), states.PENDING, text)
            with open(path, encoding="utf-8") as handle:
                job = json.load(handle)
            self.assertEqual(job["status"], claude_job.HOLD, text)
            self.assertTrue(job["hold_reason"].startswith("job_state_invalid"), job)
            notes = [e["data"] for e in events(root, path=opstate.NOTIFICATIONS)]
            self.assertEqual([n["data"].get("task_key") for n in notes if n["kind"] == "claude_job_blocked"], [bad], text)

    def test_contradictory_job_state_holds_only_that_task_until_the_file_is_deleted(self):
        capped = {"session_id": SID, "crash_resumes": recovery.MAX_INTERRUPTS, "hold_reason": "too_many_interrupts: 2"}
        variants = [dict(capped, status=s) for s in ("done", "failed", "stale", "new")] + [
            {"status": "new", "session_id": SID, "crash_resumes": 0}, {"status": "new", "session_id": None, "crash_resumes": 1},
            {"status": "new", "session_id": None, "crash_resumes": False}, {"status": "new", "session_id": None}]
        for variant in variants:
            root = tempfile.mkdtemp()
            bad, good = llm_task(root, "a"), llm_task(root, "b")
            path = claude_job.paths(root, bad)[0]
            write_json(path, dict(variant, task_key=bad))
            claude, log, env = make_fake(self, [{"do": "success"}] * 3)
            for _ in range(2):
                out = supervisor.run(root, claude_bin=claude, max_cycles=4, poll_s=0, env=env)
            self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT, variant)
            self.assertEqual(len(runs(log)), 1, variant)  # 독립 작업 b만(모순 파일로 새 세션·첫 실행을 열지 않는다)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", good)), False), states.VERIFIED, variant)
            with open(path, encoding="utf-8") as handle:
                job = json.load(handle)
            self.assertEqual((job["status"], job["hold_reason"][:17]), (claude_job.HOLD, "job_state_invalid"), variant)
            notes = [e["data"] for e in events(root, path=opstate.NOTIFICATIONS)]
            self.assertEqual([n["data"].get("task_key") for n in notes if n["kind"] == "claude_job_blocked"], [bad], variant)
            os.remove(path)  # 사람 해제(정해진 방법): 상태 파일 삭제 → 새 작업으로 다시 고른다
            supervisor.run(root, claude_bin=claude, max_cycles=4, poll_s=0, env=env)
            self.assertEqual(len(runs(log)), 2, variant)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", bad)), False), states.VERIFIED, variant)
        root = tempfile.mkdtemp()  # 정상 new(pick이 쓰는 모양: 0·null)는 그대로 첫 실행이다
        key = llm_task(root)
        write_json(claude_job.paths(root, key)[0], {"task_key": key, "status": "new", "session_id": None, "crash_resumes": 0})
        claude, log, env = make_fake(self, [{"do": "success"}])
        supervisor.run(root, claude_bin=claude, max_cycles=2, poll_s=0, env=env)
        self.assertEqual((len(runs(log)), states.state_of(states.facts(os.path.join(root, "tasks", key)), False)), (1, states.VERIFIED))

    def test_missing_null_or_bad_resume_count_counts_as_the_limit(self):
        for value in ("missing", None, "1", 1.0, True, -1, recovery.MAX_INTERRUPTS):
            root = tempfile.mkdtemp()
            llm_task(root)
            job = dict(claude_job.pick(root, 1.0), session_id=SID, status="rate_limited", crash_resumes=value)
            if value == "missing":
                job.pop("crash_resumes")
            write_json(claude_job.paths(root, job["task_key"])[0], job)
            with allow_resume(self, "misanalysis_general"):
                outcome = claude_job.execute(root, job, "claude", time.time, no_claude)
            self.assertEqual(outcome["kind"], "held", value)
            self.assertTrue(outcome["result"]["hold_reason"].startswith("too_many_interrupts"), (value, outcome))

    def test_unrecoverable_needs_the_result_session_id_to_be_the_resumed_one(self):
        exact = REAL_NO_SESSION.replace("{SID}", SID)
        real = json.loads(exact)
        self.assertTrue(claude_run.session_unrecoverable(found(exact), SID))
        other = json.dumps(dict(real, session_id="00000000-0000-4000-8000-000000000000"))
        missing = json.dumps({k: v for k, v in real.items() if k != "session_id"})
        self.assertEqual([claude_run.session_unrecoverable(found(line), SID) for line in (other, missing)], [False, False])


if __name__ == "__main__":
    unittest.main()
