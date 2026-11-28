"""VS3 필수 합성 시험 11·12와 구조: 실제 진입점 `python -m harness.supervisor`에서 사용자 추가 입력 없이
실험 VERIFIED → 분석 작업 자동 등록 → 가짜 claude의 next_plan.json → PLAN_GATE → declared.json → 다음 실험 등록(→ 가짜 executor 실행)이 이어지고,
실제 실험(./experiment·experiment_exec)은 한 번도 실행되지 않는다. 연결(C) 증거이며 실환경·활성화·모델 성능 근거가 아니다.
가짜 claude는 tests.test_harness_supervisor_kit.FAKE에 산출물 내용 지정(step.files)만 덧붙인 것이다(실제 claude·모델 호출 없음).
"""
import ast
import json
import os
import subprocess
import sys
import unittest

from harness import budget, plan_gate, sandbox, states
from harness import contract as ct
from harness.jsonio import read_json, write_json
from tests import harness_depth_kit as depth
from tests import harness_plan_gate_kit as kit
from tests.test_harness_support import REPO
from tests.test_harness_supervisor_kit import events, make_fake, runs

OLD = 'open(os.path.join(out_dir, rel), "w").write("claude:" + session)'
NEW = 'open(os.path.join(out_dir, rel), "w").write(step.get("files", {}).get(rel, "claude:" + session))'


def _fake_claude(case, steps):
    """산출물 내용을 시나리오로 정하는 가짜 claude. (실행 파일, 로그)."""
    path, log, _ = make_fake(case, steps)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    case.assertIn(OLD, text)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(OLD, NEW))
    return path, log


class EntryPointTest(unittest.TestCase):
    def test_entry_point_chains_to_the_next_experiment_without_user_input_and_runs_no_real_experiment(self):
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        root, src, head = kit.world(self)
        control = kit.control(head)
        for hid in ("H1", "H-next"):
            kit.seed(src, hid)
        write_json(os.path.join(root, "supervisor", "declared.json"), {ct.task_key(control): control})  # 사람이 한 번 등록한 대조 실험
        claude, log = _fake_claude(self, [{"do": "success", "files": {plan_gate.NEXT_PLAN: json.dumps(kit.proposal(control))}}])
        done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--claude-bin", claude, "--executors",
                               "tests.harness_plan_gate_kit:EXECUTORS", "--source-root", src, "--max-cycles", "3", "--poll", "0"],
                              cwd=REPO, capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(json.loads(done.stdout.strip().split("\n")[-1])["state"], "RUNNING")
        wanted = ("enqueued", "completed", "plan_gate_declared", "claude_job_picked", "claude_run_started")
        chain = [(e["event"], e["data"].get("task_type") or e["data"].get("task_key", "")[:8]) for e in events(root) if e["event"] in wanted]
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        [a1] = [k for k, c in tasks.items() if c["task_type"] == plan_gate.ANALYZE_TYPE]
        [e2] = [k for k, c in tasks.items() if c["depends_on"] == [a1]]
        e1 = ct.task_key(control)
        self.assertEqual(chain, [("enqueued", "experiment"), ("completed", e1[:8]), ("plan_gate_declared", plan_gate.ANALYZE_TYPE),
                                 ("enqueued", plan_gate.ANALYZE_TYPE), ("claude_job_picked", plan_gate.ANALYZE_TYPE),
                                 ("claude_run_started", a1[:8]), ("completed", a1[:8]), ("plan_gate_declared", "experiment"),
                                 ("enqueued", "experiment"), ("completed", e2[:8])], chain)
        self.assertEqual(tasks[e2]["run_conditions"]["config"]["plan"]["experiment_parameter"]["value"], 0.7)
        self.assertEqual({states.state_of(states.facts(os.path.join(root, "tasks", k)), False) for k in (e1, a1, e2)}, {states.VERIFIED})
        self.assertEqual(len(runs(log)), 1)  # 가짜 claude 1회(분석 하나)
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 2)  # 실행 직전 차감 2건(대조·다음 실험), 관문은 차감 안 함
        self.assertFalse(os.path.exists(os.path.join(src, "experiment")))  # 실제 ./experiment 없음: 실제 실험 실행 0건
        self.assertEqual(len(os.listdir(os.path.join(src, "artifacts", "experiments"))), 2)  # 심은 기록뿐(새 실험 기록 없음)

    def test_without_an_executor_table_the_gate_registers_but_nothing_is_executed(self):
        root, src, head = kit.world(self)
        control = kit.control(head)
        e1 = kit.verified(root, src, control)
        claude, log = _fake_claude(self, [{"do": "success", "files": {plan_gate.NEXT_PLAN: json.dumps(kit.proposal(control))}}])
        done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--claude-bin", claude, "--source-root", src,
                               "--max-cycles", "3", "--poll", "0"], cwd=REPO, capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(json.loads(done.stdout.strip().split("\n")[-1])["python_runs"], 0)
        [e2] = [k for k in os.listdir(os.path.join(root, "tasks")) if read_json(os.path.join(root, "tasks", k, "contract.json"))["depends_on"]
                and read_json(os.path.join(root, "tasks", k, "contract.json"))["task_type"] == "experiment"]
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", e2)), False), states.PENDING)  # 등록만, 실행 0건
        self.assertEqual([e["data"]["task_key"] for e in events(root, "claimed") if e["data"]["task_key"] == e2], [])
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 1)  # 대조 실험(합성 drain) 1건뿐
        self.assertTrue(e1)

    def test_structure_function_counts_and_call_depth(self):
        graph = depth.call_graph()
        for name, limit in (("supervisor.run", 4), ("plan_gate.gate", 3), ("runner.main", 4), ("graph.register_missing", 3)):
            self.assertLessEqual(depth.longest(name, graph)[0], limit, depth.longest(name, graph))
        for rel in ("harness/plan_gate.py", "harness/supervisor.py", "harness/runner.py", "harness/dedupe.py", "tests/harness_plan_gate_kit.py",
                    "tests/test_harness_vs3_gate.py", "tests/test_harness_vs3_gate_flow.py", "tests/test_harness_vs3_entry.py",
                    "tests/test_harness_vs3_doc_commit.py"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(tree))
            self.assertLessEqual(count, 7, rel)


if __name__ == "__main__":
    unittest.main()
