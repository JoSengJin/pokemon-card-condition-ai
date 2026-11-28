"""B5-11 합성 종단(C 증거): 실제 진입점 `python -m harness.supervisor` **한 번의 실행(3회차)**에서 사용자 추가 입력 없이
실험 VERIFIED → 분석(가짜 claude) → PLAN_GATE → 다음 실험 선언·등록·실행, 그리고 학습 VERIFIED → 모델 등록 → 의존한 평가 등록·실행 → 채점·승격 판정(기록만)이 이어진다.
회차가 3인 이유: 의존 선언(분석·평가·다음 실험)은 의존 작업이 VERIFIED가 된 다음 회차 시작에 등록된다(graph.register_missing·plan_gate.gate 설계).
**이 시험이 아닌 것**: 실제 ./experiment·실제 claude·실제 학습·평가·승격·모델·네트워크 호출은 0건이다(가짜 executor·가짜 claude, 합성 구역 행).
B5-9(Silver·능동 학습·감사)는 입력 없음으로 미구현이라 범위 밖이다. 합성 통과는 실제 실험·다음 가설·학습·평가 검증이나 모델 성능 근거가 아니다.
끊긴 곳(실제 어댑터 경로): experiment_exec는 sandbox 안에서 원본 저장소 artifacts/에 못 써 실험 기록을 남기는 실행이 결과 불명이 되므로 실험→분석 연결이 시작되지 않는다(둘째 시험).
"""
import ast
import os
import subprocess
import sys
import unittest

from harness import apply_promote, budget, ledger, plan_gate, registry, sandbox, states
from harness import contract as ct
from harness.jsonio import read_json, write_json
from tests import harness_b5_e2e_kit as kit
from tests import harness_depth_kit as depth
from tests.test_harness_b5_experiment_run import NOW, _task, _world
from tests.test_harness_support import REPO
from tests.test_harness_supervisor_kit import events, runs


def _state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class SyntheticEndToEndTest(unittest.TestCase):
    def test_one_supervisor_run_chains_experiment_analysis_next_plan_training_evaluation_and_verdict(self):
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        root, src, out, log, keys = kit.chain(self)
        self.assertEqual((out["state"], out["cycles"], out["claude_runs"], out["outcomes"]), ("RUNNING", 3, 1, ["done"]), out)
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        [a1] = [k for k, c in tasks.items() if c["task_type"] == plan_gate.ANALYZE_TYPE]
        [e2] = [k for k, c in tasks.items() if c["task_type"] == "experiment" and c["depends_on"] == [a1]]
        self.assertEqual(sorted(tasks), sorted([keys["e1"], keys["train"], keys["eval"], a1, e2]))
        self.assertEqual({_state(root, k) for k in tasks}, {states.VERIFIED})
        order = [(e["event"], e["data"].get("task_key")) for e in events(root)]
        at = {name: order.index(name) for name in (("completed", keys["e1"]), ("plan_gate_declared", a1), ("completed", a1), ("plan_gate_declared", e2),
                                                   ("completed", e2), ("completed", keys["train"]), ("enqueued", keys["eval"]),
                                                   ("completed", keys["eval"]))}
        self.assertLess(at["completed", keys["e1"]], at["plan_gate_declared", a1])  # 실험 → 분석 선언
        self.assertLess(at["plan_gate_declared", a1], at["completed", a1])  # 분석(가짜 claude) 실행
        self.assertLess(at["completed", a1], at["plan_gate_declared", e2])  # 분석 → 다음 실험 선언(PLAN_GATE)
        self.assertLess(at["plan_gate_declared", e2], at["completed", e2])  # 다음 실험 실행
        self.assertLess(at["completed", keys["train"]], at["enqueued", keys["eval"]])  # 학습 VERIFIED → 의존한 평가 등록
        self.assertLess(at["enqueued", keys["eval"]], at["completed", keys["eval"]])
        [model] = registry.load(root)["models"]  # 학습 → 모델 등록 1건
        self.assertEqual([(r["kind"], r["task_key"]) for e in events(root, "apply_drain") for r in e["data"]["results"]],
                         [("train", keys["train"]), ("promote", keys["eval"])])
        verdict = read_json(os.path.join(root, apply_promote.VERDICTS, keys["eval"] + ".json"))
        self.assertEqual((verdict["model_id"], verdict["verdict"], verdict["promoted"]), (model, "통과", False))  # 판정만, 승격 실행 없음
        self.assertEqual(events(root, "champion_promoted"), [])
        self.assertEqual(tasks[e2]["run_conditions"]["config"]["plan"]["experiment_parameter"]["value"], 0.7)  # 다음 가설(변수 하나)
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 4)  # 실험 2·학습 1·평가 1: runner가 실험·학습·평가 실행 시작마다 1건(분석은 Claude 작업이라 아님)
        self.assertEqual((len(runs(log)), os.path.exists(os.path.join(src, "experiment"))), (1, False))  # 가짜 claude 1회, 실제 ./experiment 없음
        self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])

    def test_real_adapter_in_the_sandbox_cannot_record_so_the_chain_stops_at_the_first_experiment(self):
        """끊긴 곳 1(알려진 것, D안: 실제 연결은 첫 실험 승인 뒤): 실제 어댑터(harness.experiment_exec) + 가짜 ./experiment를 진입점에서 돌리면 sandbox가
        원본 저장소 쓰기를 막아 실험이 결과 불명(INTERRUPTED)이 되고, 분석·다음 선언·평가로 이어지는 줄이 하나도 생기지 않는다(연결이 시작되지 않는다)."""
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        root, src, head = _world(self)
        task = _task(head, "completed")
        write_json(os.path.join(root, "supervisor", "declared.json"), {ct.task_key(task): task})
        done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--executors", "harness.experiment_exec:EXECUTORS",
                               "--source-root", src, "--max-cycles", "2", "--poll", "0"], cwd=REPO, capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        self.assertEqual(_state(root, ct.task_key(task)), states.INTERRUPTED)
        names = {e["event"] for e in events(root)}
        self.assertFalse(names & {"plan_gate_declared", "apply_drain", "promotion_verdict", "claude_job_picked"}, names)
        self.assertEqual([k for k in os.listdir(os.path.join(root, "tasks"))], [ct.task_key(task)])  # 분석 작업도 등록되지 않았다
        self.assertFalse(os.path.exists(os.path.join(src, "artifacts")))

    def test_structure_function_counts_and_call_depth(self):
        graph = depth.call_graph()
        for name in ("supervisor.run", "plan_gate.gate", "apply_main.pending"):
            self.assertLessEqual(depth.longest(name, graph)[0], 4, depth.longest(name, graph))
        for rel in ("tests/harness_b5_e2e_kit.py", "tests/test_harness_b5_e2e_synthetic.py"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
                count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(ast.parse(handle.read())))
            self.assertLessEqual(count, 7, rel)


if __name__ == "__main__":
    unittest.main()
