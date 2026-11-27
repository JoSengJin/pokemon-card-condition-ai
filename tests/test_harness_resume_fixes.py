"""검증 결함 F4·F5·N1과 4단계 '세션 복원 불가 확인'(가짜 claude = 실제 하위 프로세스).

F4 매 실행 직전에 이전 Claude 완료 선언을 지우고, 선언에 이번 실행의 run_token이 있어야 완료로 본다(성공 종료 + 낡은 선언 → 대기).
F5 초기화 시각 미상 한도의 시도 횟수는 작업이 아니라 전체에서 이어 센다: 독립 작업이 바뀌어도 처음 1회 + 3회 뒤 정지, 성공하면 초기화.
N1 재실행 안전으로 등록하지 않은 작업은 완료 기록이 손상되고 복구할 수 없어도 자동 재실행하지 않고 대기한다(완료 기록 보존).
4단계 session_unrecoverable은 실환경에서 확보한 정확한 형식(c-realenv/t4-bogus-resume.jsonl, ID만 바꿈)만 True이고, True일 때만 새 세션을 연다.
"""
import json
import os
import pathlib
import tempfile
import unittest

from harness import cas, claude_job, claude_run, opstate, queue, ratelimit, states, supervisor
from harness import contract as ct
from harness.jsonio import read_json
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_support import BOOT, claim, finish, make_contract
from tests.test_harness_supervisor_kit import Clock, events, llm_task, make_fake, runs

# Claude Code 2.1.310 실제 출력(없는 세션 --resume, 종료 코드 1). 세션 ID 자리만 {SID}로 바꿨다.
REAL_NO_SESSION = (
    '{"type":"result","subtype":"error_during_execution","duration_ms":0,"duration_api_ms":0,"is_error":true,"num_turns":0,'
    '"stop_reason":null,"session_id":"{SID}","total_cost_usd":0,"usage":{"output_tokens_details":{"thinking_tokens":0},'
    '"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":'
    '{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,'
    '"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","fallback_credit":null},"modelUsage":{},'
    '"permission_denials":[],"uuid":"6260c58a-fa2f-4b83-831c-3b9650f19361","errors":["No conversation found with session ID: {SID}"],'
    '"result_index":0}')
SID = "11111111-2222-4333-8444-555555555555"


def state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


def found(line, code=1):
    """claude_run.run_once와 같은 모양의 결과(ratelimit.scan + 종료 코드)."""
    return dict(ratelimit.scan([line], code), returncode=code)


class ResumeFixTest(unittest.TestCase):
    def test_f4_stale_or_foreign_declaration_is_not_accepted(self):
        for step in ({"do": "noop"}, {"do": "success", "token": "f" * 32}):  # 아무것도 안 하고 성공 종료 / 다른 실행의 토큰
            root = tempfile.mkdtemp()
            claude, log, env = make_fake(self, [step])
            key = queue.enqueue(root, dict(make_contract("s", task_type="misanalysis_general", needs_llm=True), inputs={},
                                           outputs=["a.md", "b.md"]), 1.0)
            out = os.path.join(root, "tasks", key, "out")
            os.makedirs(out)
            pathlib.Path(out, "a.md").write_text("이전 실행이 반쯤 쓴 내용")
            pathlib.Path(out, "b.md").write_text("")
            pathlib.Path(out, ct.DECLARATION).write_text(json.dumps({"task_key": key, "outputs": ["a.md", "b.md"]}))
            supervisor.run(root, claude_bin=claude, max_cycles=2, poll_s=0, env=env)
            with open(claude_job.paths(root, key)[0]) as handle:
                job = json.load(handle)
            self.assertEqual((state(root, key), job["status"]), (states.PENDING, "blocked"), step)
            self.assertTrue(job["hold_reason"].startswith("completion_marker_missing"), job)
            self.assertEqual(len(runs(log)), 1)
            if step["do"] == "noop":  # 실행 직전에 이전 선언을 지웠다
                self.assertFalse(os.path.exists(os.path.join(out, ct.DECLARATION)))

    def test_f5_unknown_reset_attempts_are_counted_across_tasks_and_reset_by_success(self):
        root = tempfile.mkdtemp()
        keys = [llm_task(root, "t%d" % i) for i in range(6)]
        self.assertEqual(len(set(keys)), 6)
        claude, log, env = make_fake(self, [{"do": "limit", "reset": "none"}] * 10)
        clock = Clock(1_000_000.0)
        supervisor.run(root, claude_bin=claude, max_cycles=40, poll_s=10 ** 6, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
        self.assertEqual(len(runs(log)), 4)  # 처음 1회 + 다시 시도 3회(작업이 바뀌어도 이어 센다), 그 뒤 정지
        starts = [e["ts"] for e in events(root, "claude_run_started")]
        for gap, want in zip([b - a for a, b in zip(starts, starts[1:])], (900, 5 * 3600, 8 * 86400)):
            self.assertGreaterEqual(gap, want)
            self.assertLess(gap, want + 1)
        [info] = opstate.load(root)["conditions"].values()
        self.assertTrue(info["exhausted"])
        self.assertEqual([e["data"]["kind"] for e in events(root, path=opstate.NOTIFICATIONS)].count("rate_limit_unknown_exhausted"), 1)
        root = tempfile.mkdtemp()  # 성공한 실행이 있으면 초기화한다
        first, second = llm_task(root, "a"), llm_task(root, "b")
        claude, log, env = make_fake(self, [{"do": "limit", "reset": "none"}, {"do": "success"}])
        clock = Clock(1_000_000.0)
        supervisor.run(root, claude_bin=claude, max_cycles=1, poll_s=60, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
        self.assertEqual(read_json(os.path.join(root, claude_job.UNKNOWN_LIMIT))["attempts"], 1)
        supervisor.run(root, claude_bin=claude, max_cycles=40, poll_s=60, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
        self.assertEqual(sorted([state(root, first), state(root, second)]), [states.PENDING, states.VERIFIED])
        self.assertEqual(read_json(os.path.join(root, claude_job.UNKNOWN_LIMIT))["attempts"], 0)

    def test_n1_unrecoverable_corrupt_unregistered_task_waits_and_keeps_its_record(self):
        root = tempfile.mkdtemp()
        key, _ = finish(root, make_contract("a"), 1.0, payload=b"original")
        task_dir = os.path.join(root, "tasks", key)
        recorded = json.loads(pathlib.Path(task_dir, "done.json").read_text())["manifest"]["result.txt"]
        pathlib.Path(cas.blob_path(os.path.join(root, "cas"), recorded)).write_bytes(b"also damaged")
        pathlib.Path(task_dir, "out", "result.txt").write_bytes(b"originaX")
        plans = [claim(root, key, os.getpid(), BOOT, 10.0 + i) for i in range(2)]
        self.assertEqual([(p["ok"], p["reason"]) for p in plans], [(False, "await_result")] * 2)
        self.assertTrue(os.path.exists(os.path.join(task_dir, "done.json")))  # 보관(history)으로 옮겨 PENDING이 되지 않는다
        self.assertEqual(state(root, key), states.CORRUPT)
        [record] = [e["data"] for e in events(root, "awaiting_result")]
        self.assertEqual(record["reason"], "corrupt_unrecoverable")

    def test_session_unrecoverable_accepts_only_the_exact_real_output(self):
        exact = REAL_NO_SESSION.replace("{SID}", SID)
        self.assertTrue(claude_run.session_unrecoverable(found(exact), SID))
        real = json.loads(exact)
        near = [found(exact, 0), found(exact, 2), found(exact.replace(SID, SID[:-1] + "6")),
                found(json.dumps(dict(real, subtype="error"))), found(json.dumps(dict(real, is_error=False))),
                found(json.dumps(dict(real, num_turns=1))), found(json.dumps(dict(real, errors=real["errors"] + ["x"]))),
                found(json.dumps(dict(real, errors=["no conversation found with session ID: " + SID]))),
                found(json.dumps(dict(real, errors=[]))), found(json.dumps(dict(real, num_turns=False))), found("")]
        self.assertEqual([claude_run.session_unrecoverable(f, SID) for f in near], [False] * len(near))
        self.assertFalse(claude_run.session_unrecoverable(found(exact), "other-id"))

    def test_confirmed_unrecoverable_session_opens_a_new_session_once(self):
        root = tempfile.mkdtemp()
        steps = [{"do": "limit", "after": 1}, {"do": "raw", "line": REAL_NO_SESSION, "code": 1}, {"do": "success"}]
        claude, log, env = make_fake(self, steps)
        key = llm_task(root)
        with allow_resume(self, "misanalysis_general"):
            out = supervisor.run(root, claude, max_cycles=5, poll_s=3, env=env)
        first, failed, fresh = runs(log)
        self.assertEqual(failed["resume"], first["session_id"])
        self.assertTrue(fresh["session_id"] and fresh["session_id"] != first["session_id"] and fresh["resume"] is None)
        self.assertIn(first["session_id"], fresh["prompt"])  # 이어받지 못한 세션과 장부를 가리키는 새 세션 프롬프트
        self.assertEqual((state(root, key), out["outcomes"]), (states.VERIFIED, ["rate_limited", "done"]))


if __name__ == "__main__":
    unittest.main()
