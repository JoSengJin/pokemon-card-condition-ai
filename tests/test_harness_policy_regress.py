"""재현된 정책 위반 R1~R5 회귀 시험(2단계). 가짜 claude(실제 하위 프로세스)와 kill -9 주입을 쓴다.

R1 등록하지 않은 유형의 중단·일시 실패 작업은 자동 재실행하지 않는다 / R2 실행 조건이 같은 실험은 설명 문구가 달라도 중복 등록 거절 /
R3 Claude가 끝낸 뒤 Supervisor가 죽어도 다시 --resume하지 않는다 / R4 한도가 아닌 --resume 실패 뒤 새 세션을 열지 않는다 /
R5 원인 불명 실패 1건이 다른 독립 Claude 작업을 막지 않는다.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

from harness import contract as ct
from harness import queue, states, supervisor
from tests.test_harness_support import BOOT, claim, dead_lease, make_contract
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_supervisor_kit import REPO, llm_task, make_fake, runs

T0 = 1_800_000_000.0
KILL_AT_SETTLE = r'''
import os, sys
from harness import claude_job, supervisor
claude_job.settle = lambda *a, **k: os.kill(os.getpid(), 9)  # claude가 끝난 직후, 결과 반영 전에 Supervisor kill -9
supervisor.run(sys.argv[1], sys.argv[2], max_cycles=1)
'''


def state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class PolicyRegressionTest(unittest.TestCase):
    def test_r1_interrupted_or_transient_failed_unregistered_task_is_not_rerun(self):
        root = tempfile.mkdtemp()
        key = queue.enqueue(root, make_contract("r1"), T0)
        dead_lease(root, key, T0, run_id="ab12")  # 2시간 전에 시작해 끊긴 실행
        res = claim(root, key, os.getpid(), BOOT, T0 + 7200)
        self.assertEqual((res["ok"], res["reason"]), (False, "await_result"))
        other = queue.enqueue(root, make_contract("r1b"), T0)
        first = claim(root, other, os.getpid(), BOOT, T0)  # 첫 실행은 막지 않는다
        self.assertTrue(first["ok"])
        queue.fail(root, other, first["run_id"], first["lease"], "transient", "ConnectionError", T0 + 1)
        again = claim(root, other, os.getpid(), BOOT, T0 + 2)
        self.assertEqual((again["ok"], again["reason"]), (False, "await_result"))

    def test_r2_same_run_conditions_with_different_wording_is_refused(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(src, "data"))  # 입력은 실제 파일과 대조한다(검증 결함 F3)
        with open(os.path.join(src, "data", "a.json"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        sha = hashlib.sha256(b"{}").hexdigest()
        base = make_contract("x", task_type="experiment", inputs={"data/a.json": sha})
        base["run_conditions"] = {"command": ["python", "train.py", "{input:data/a.json}"], "code_sha": "c" * 40, "seed": 1,
                                  "hypothesis_id": "H-1", "input_roles": {"data/a.json": "data"}}  # 입력은 자리표시자로 참조(2차 G4)
        first = queue.enqueue(root, base, T0, source_root=src)
        variants = [dict(base, risk="high"), dict(base, retry_policy={"max_transient_retries": 0}),
                    dict(base, escalation_level=2),
                    dict(base, inputs={"./data/a.json": sha}, run_conditions=dict(base["run_conditions"], input_roles={"./data/a.json": "data"})),
                    dict(base, run_conditions=dict(base["run_conditions"], hypothesis_id="H-2", description="다른 설명"))]
        for variant in variants:
            with self.assertRaises(queue.DuplicateTask) as caught:
                queue.enqueue(root, variant, T0 + 1, source_root=src)
            self.assertEqual(caught.exception.existing, first)
        with self.assertRaises(ct.ContractError):  # 실행 조건이 없어 중복을 판별할 수 없는 실험은 등록 거절
            queue.enqueue(root, make_contract("y", task_type="experiment"), T0)
        other = dict(base, run_conditions=dict(base["run_conditions"], seed=2))
        self.assertNotEqual(queue.enqueue(root, other, T0, source_root=src), first)  # 조건 하나라도 다르면 통과
        self.assertEqual(queue.enqueue(root, base, T0 + 3, source_root=src), first)  # 같은 계약은 그대로 멱등

    def test_r3_finished_claude_work_is_not_resumed_after_supervisor_death(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success"}, {"do": "success"}])
        key = llm_task(root)
        subprocess.run([sys.executable, "-c", KILL_AT_SETTLE, root, claude], cwd=REPO, env=env, check=False, timeout=60)
        self.assertEqual(len(runs(log)), 1)
        supervisor.run(root, claude, max_cycles=3, poll_s=0.1, env=env)
        self.assertEqual((len(runs(log)), state(root, key)), (1, states.VERIFIED))

    def test_r4_resume_failure_without_rate_limit_does_not_open_a_new_session(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "limit", "after": 1}, {"do": "no_session"}, {"do": "success"}])
        key = llm_task(root)
        with allow_resume(self, "misanalysis_general"):
            supervisor.run(root, claude, max_cycles=5, poll_s=3, env=env)
        self.assertEqual([r["resume"] is not None for r in runs(log)], [False, True])  # 새 세션(--session-id) 재실행 없음
        self.assertEqual(state(root, key), states.PENDING)

    def test_r5_unknown_failure_holds_only_that_task(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "fail"}, {"do": "success"}])
        keys = sorted([llm_task(root), llm_task(root, task_type="experiment_log_summary")])  # 서로 독립인 두 작업
        supervisor.run(root, claude, max_cycles=4, poll_s=0.1, env=env)
        self.assertEqual([state(root, k) for k in keys], [states.PENDING, states.VERIFIED])
        self.assertEqual(len(runs(log)), 2)


if __name__ == "__main__":
    unittest.main()
