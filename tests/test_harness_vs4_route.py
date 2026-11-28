"""VS4: claude_job의 라우팅 실패 이력(B5-6) 연결. 합성 root·가짜 claude만 쓴다(실제 claude·모델 호출 없음). 합성 통과는 모델 정확도 근거가 아니다.

**검사 작업의 실행은 합성이다**: runner는 LLM 작업에 의존하는 Python 작업을 (그 LLM 작업이 VERIFIED여도) 실행하지 않는다(runner._scan, 2단계
계약). 그래서 judge()가 runner와 같은 큐 API(claim → 산출물 → 완료 표시 → complete)로 '항상 미달' 판정을 남긴다. 검사 실행기가 아니다.
검사 작업의 등록(declared.json → graph.register_missing)과 이력 읽기·라우팅·대기는 실제 진입점 python -m harness.supervisor가 한다.
"""
import ast
import json
import os
import subprocess
import tempfile
import time
import unittest

from harness import contract as ct
from harness import claude_job, lease, manifest, opstate, queue, route_history, states, supervisor
from harness.jsonio import read_json, write_json
from tests import harness_depth_kit as kit
from tests.test_harness_supervisor_kit import SUPERVISOR, events, make_fake, runs
from tests.test_harness_support import REPO, make_contract


def judge(root, key):
    """등록된 검사 작업을 runner와 같은 큐 API로 완료한다: 의존한 작업을 quality_gate_miss로 판정."""
    task_dir = os.path.join(root, "tasks", key)
    task, got = read_json(os.path.join(task_dir, "contract.json")), queue.claim(root, key, os.getpid(), lease.boot_id(), time.time())
    out = os.path.join(task_dir, "out")
    os.makedirs(out, exist_ok=True)
    write_json(os.path.join(out, route_history.VERDICT), {"target_task_key": task["depends_on"][0], "cause": "quality_gate_miss",
                                                         "ruled_out": list(route_history.RULED_OUT)})
    write_json(os.path.join(task_dir, ct.COMPLETION), {"task_key": key, "outputs": manifest.build(out, task["outputs"])})
    queue.complete(root, key, got["run_id"], got["lease"], time.time())


def chain(attempts):
    """declared.json 내용: 시도 → 검사 → 재시도 …(시도 attempts개). (선언 dict, 시도 키 목록, 검사 키 목록)."""
    declared, tries, gates = {}, [], []
    for n in range(attempts):
        for task in ([make_contract("g", depends_on=[tries[-1]], task_type="quality_gate", outputs=(route_history.VERDICT,))]
                     if n else []) + [None]:
            if task is None:
                task = dict(make_contract("a", depends_on=gates[-1:], task_type="misanalysis_general", needs_llm=True,
                                          outputs=("a.md",)), inputs={})
                tries.append(ct.task_key(task))
            else:
                gates.append(ct.task_key(task))
            declared[ct.task_key(task)] = task
    return declared, tries, gates


class RouteConnectTest(unittest.TestCase):
    def test_checker_types_register_without_a_mock_but_never_with_run_conditions(self):
        root = tempfile.mkdtemp()
        for kind in route_history.CHECKER_TYPES:
            key = queue.enqueue(root, make_contract("c", task_type=kind), 1.0)
            self.assertEqual(states.facts(os.path.join(root, "tasks", key))["contract"]["task_type"], kind)
            for bad in (make_contract("x", task_type=kind.upper()),
                        dict(make_contract("y", task_type=kind), run_conditions={"command": ["python"]})):
                with self.assertRaises(ct.ContractError):
                    queue.enqueue(root, bad, 2.0)

    def test_entrypoint_escalates_by_checker_history_and_holds_the_pending_job_only(self):
        root, (claude, log, env) = tempfile.mkdtemp(), make_fake(self, [{"do": "success"}] * 8)
        declared, tries, gates = chain(4)
        other = dict(make_contract("o", depends_on=gates[-1:], task_type="experiment_log_summary", needs_llm=True,
                                   outputs=("o.md",)), inputs={})  # 같은 검사 작업에 의존해도 유형이 다르면 이력이 아니다
        declared[ct.task_key(other)] = other
        write_json(os.path.join(root, supervisor.DECLARED), declared)
        argv = SUPERVISOR + ["--root", root, "--claude-bin", claude, "--max-cycles", "1", "--poll", "0"]
        said, waiting = [], list(gates)
        for _ in range(10):  # 진입점 1회차씩: 등록 → claude 작업 하나. 등록된 검사 작업만 사이에서 합성 완료한다
            done = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            said.append(done.stdout.strip())
            if waiting and os.path.isdir(os.path.join(root, "tasks", waiting[0])):
                judge(root, waiting.pop(0))
        if os.environ.get("VS4_EVIDENCE"):
            print(json.dumps({"argv": argv, "stdout": said, "root": root, "tries": tries, "other": ct.task_key(other)}))
        by_key = {}
        for row in events(root, "claude_run_started"):
            by_key.setdefault(row["data"]["task_key"], []).append((row["data"]["model"], row["data"]["effort"]))
        self.assertEqual([by_key.get(k) for k in tries], [[("sonnet", "medium")], [("sonnet", "high")], [("opus", "high")], None])
        self.assertEqual(by_key.get(ct.task_key(other)), [("haiku", "low")])  # 대기는 그 작업만
        self.assertEqual((waiting, len(runs(log))), ([], 4))
        self.assertNotIn("xhigh", [r["effort"] for r in runs(log)])
        job = read_json(claude_job.paths(root, tries[3])[0])
        self.assertEqual((job["status"], job["hold_reason"].split(":")[0], job["session_id"]), ("blocked", "route_pending", None))
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", tries[3])), False), states.PENDING)
        last = [r["data"] for r in events(root, "route_decision") if r["data"]["task_key"] == tries[3]]
        self.assertEqual([(d["pending"], d["applied"], len(d["escalations"])) for d in last], [(True, None, 2)])
        self.assertEqual(opstate.effective(opstate.load(root)), opstate.RUNNING)

    def test_damaged_history_holds_that_job_instead_of_falling_back_to_the_base_model(self):
        root, (claude, log, env) = tempfile.mkdtemp(), make_fake(self, [{"do": "success"}] * 4)
        declared, tries, gates = chain(2)
        write_json(os.path.join(root, supervisor.DECLARED), declared)
        supervisor.run(root, claude, max_cycles=2, poll_s=0, env=env)
        judge(root, gates[0])
        os.remove(os.path.join(root, "tasks", tries[0], "out", "a.md"))  # 판정 대상의 산출물이 사라졌다
        free = dict(make_contract("f", task_type="repeated_failure_analysis", needs_llm=True, outputs=("f.md",)), inputs={})
        free_key = queue.enqueue(root, free, 5.0)
        got = supervisor.run(root, claude, max_cycles=4, poll_s=0, env=env)
        job = read_json(claude_job.paths(root, tries[1])[0])
        self.assertEqual((job["status"], job["hold_reason"].split(":")[0]), ("blocked", "route_history_invalid"), job)
        self.assertEqual(sorted(r["data"]["task_key"] for r in events(root, "claude_run_started")), sorted([tries[0], free_key]))
        self.assertEqual(got["state"], opstate.RUNNING)

    def test_call_depth_and_function_count_stay_within_the_limit(self):
        for name, limit in (("claude_job.execute", 3), ("supervisor.run", 4)):
            depth, path = kit.longest(name)
            self.assertLessEqual(depth, limit, path)
        with open(os.path.join(REPO, "harness", "claude_job.py"), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        self.assertLessEqual(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(tree)), 7)


if __name__ == "__main__":
    unittest.main()
