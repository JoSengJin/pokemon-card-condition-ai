"""VS5 연결(C) 시험: 실제 진입점 `python -m harness.supervisor` 한 번 실행(2회차)에서 사용자 추가 입력 없이
학습 VERIFIED → 적용기(별도 프로세스)의 모델 등록 → (다음 회차: 의존한 평가 등록·실행) → 채점·승격 판정(기록만)이 이어진다.
(의존 선언은 의존 작업이 VERIFIED가 된 뒤 다음 회차에 등록된다: graph.register_missing 설계. 그래서 2회차가 필요하다.)
실제 학습·평가·승격·모델·네트워크 호출 없음(가짜 executor, 합성 구역 행). 연결 증거이며 실환경·활성화·모델 성능 근거가 아니다.
"""
import ast
import json
import os
import subprocess
import sys
import unittest

from harness import apply_promote, ledger, opstate, registry, sandbox, states
from harness import contract as ct
from harness.jsonio import read_json
from tests import harness_depth_kit as depth
from tests import harness_vs5_kit as kit
from tests import harness_vs5_run as run
from tests.test_harness_support import REPO
from tests.test_harness_supervisor_kit import events


def supervise(root, src, *extra):
    done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--executors", "tests.harness_vs5_kit:EXECUTORS",
                           "--source-root", src, "--max-cycles", "2", "--poll", "0"] + list(extra), cwd=REPO, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-1500:]
    return json.loads(done.stdout.strip().split("\n")[-1])


class EntryPointTest(unittest.TestCase):
    def setUp(self):
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        self.root, self.src, self.head = run.world(self)
        self.train = kit.training(self.head)
        self.tkey = ct.task_key(self.train)
        self.eval = kit.evaluation(self.head, self.tkey)
        self.ekey = ct.task_key(self.eval)
        run.declare(self.root, self.train, self.eval)  # 사람이 한 번 쓰는 선언(학습·평가 계약)

    def test_first_cycle_runs_training_then_registers_then_judges_without_promoting(self):
        out = supervise(self.root, self.src)
        self.assertEqual((out["state"], out["cycles"], len(out["applied"])), ("RUNNING", 2, 2))
        names = [e["event"] for e in events(self.root) if e["event"] in ("enqueued", "completed", "apply_drain", "promotion_verdict", "champion_promoted")]
        self.assertEqual(names, ["enqueued", "completed", "apply_drain", "enqueued", "completed", "promotion_verdict", "apply_drain"])  # 실행 뒤에 적용
        [(model, rec)] = registry.load(self.root)["models"].items()
        self.assertEqual((rec["parent"], rec["grade"]), (None, "Challenger"))
        drains = events(self.root, "apply_drain")
        self.assertEqual([[(r["kind"], r["task_key"], r["ok"]) for r in d["data"]["results"]] for d in drains],
                         [[("train", self.tkey, True)], [("promote", self.ekey, True)]])
        verdict = read_json(os.path.join(self.root, apply_promote.VERDICTS, self.ekey + ".json"))
        self.assertEqual((verdict["model_id"], verdict["verdict"], verdict["promoted"]), (model, "통과", False))
        self.assertEqual(events(self.root, "promotion_verdict")[0]["data"]["model_id"], model)
        self.assertEqual({states.state_of(states.facts(os.path.join(self.root, "tasks", k)), False) for k in (self.tkey, self.ekey)}, {states.VERIFIED})
        self.assertEqual(supervise(self.root, self.src)["state"], "RUNNING")  # 다시 돌려도 새 등록·판정·장부 줄이 없다
        self.assertEqual((len(registry.load(self.root)["models"]), len(events(self.root, "apply_drain")), len(events(self.root, "promotion_verdict"))), (1, 2, 1))
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])

    def test_stopped_state_blocks_every_apply_and_a_broken_registry_halts_the_supervisor(self):
        run.run_all(self)  # 가짜 executor로 학습·평가를 VERIFIED까지(적용 전)
        opstate.set_condition(self.root, opstate.USER_STOPPED, 9.0, "user", "정지")
        self.assertEqual(supervise(self.root, self.src)["state"], "USER_STOPPED")
        self.assertEqual((os.path.exists(os.path.join(self.root, "models")), events(self.root, "apply_drain")), (False, []))  # 정지 중 반영 없음
        opstate.clear_by_user(self.root, opstate.USER_STOPPED, 10.0, "재개")
        os.makedirs(os.path.join(self.root, "models"))
        with open(os.path.join(self.root, registry.REGISTRY), "w", encoding="utf-8") as handle:
            handle.write("not a ledger line\n")  # 등록 장부 손상: 추정하지 않고 멈춘다
        self.assertEqual(supervise(self.root, self.src)["state"], "INTEGRITY_HALT")
        self.assertEqual(events(self.root, "promotion_verdict"), [])

    def test_structure_function_counts_and_call_depth(self):
        graph = depth.call_graph()
        for name, limit in (("supervisor.run", 4), ("apply_promote.apply", 4), ("apply_main.pending", 2), ("apply_train.apply", 4)):
            self.assertLessEqual(depth.longest(name, graph)[0], limit, depth.longest(name, graph))
        for rel in ("harness/apply_main.py", "harness/apply_promote.py", "harness/supervisor.py", "tests/harness_vs5_kit.py", "tests/harness_vs5_run.py",
                    "tests/test_harness_vs5_apply.py", "tests/test_harness_vs5_entry.py"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
                count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(ast.parse(handle.read())))
            self.assertLessEqual(count, 7, rel)


if __name__ == "__main__":
    unittest.main()
