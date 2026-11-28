"""B5-4·B5-8 연결: runner가 실험 executor(harness.experiment_exec:EXECUTORS) 직전에 실험 예산을 논리 실험 키로 차감하고, 실행되지 않았음이
확인된 경우(대조·사본 실패, 어댑터 not_started·refused)에만 그 시도의 새 차감을 취소한다. 결과 불명·실험 실패는 차감을 유지한다.
재시도·kill·실제 진입점(sandbox)은 test_harness_b5_experiment_run_faults.

가짜 experiment(tests.test_harness_b5_experiment_exec.FAKE)를 커밋한 임시 git 원본만 쓴다. **실제 ./experiment 연결: 미완료**(sandbox 안에서는
저장소 artifacts/에 쓸 수 없어 실험 기록을 남기는 실행은 결과 불명이 된다. 진입점 시험이 그 사실을 고정한다). 합성 통과는 모델 성능 근거가 아니다.
"""
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from harness import budget, dedupe, experiment_exec, opstate, queue, runner, states
from tests import harness_depth_kit as kit
from tests.test_harness_b5_experiment_exec import FAKE
from tests.test_harness_supervisor_kit import events

NOW = 1_894_000_000.0  # 2030-01 수요일 무렵(주 경계와 멀다)
CLOCK = functools.partial(float, NOW)  # 고정 시각(lambda 대신: 파일 함수 수 제한)
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _world(case):
    """(하네스 root, 가짜 experiment를 커밋한 원본 저장소, HEAD). 정리는 case에 등록한다."""
    base = tempfile.mkdtemp(prefix="b5-run-")
    case.addCleanup(shutil.rmtree, base, True)
    src, root = os.path.join(base, "src"), os.path.join(base, "root")
    os.makedirs(src)
    with open(os.path.join(src, "experiment"), "w", encoding="utf-8") as handle:
        handle.write(FAKE % {"python": sys.executable})
    os.chmod(os.path.join(src, "experiment"), 0o755)
    with open(os.path.join(src, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("artifacts/\n")
    for step in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fake"]):
        subprocess.run(GIT + ["-C", src] + step, check=True, capture_output=True)
    head = subprocess.run(GIT + ["-C", src, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return root, src, head


def _task(head, mode, seed=1):
    return {"task_type": "experiment", "inputs": {}, "outputs": list(experiment_exec.OUTPUTS), "depends_on": [], "needs_llm": False,
            "needs_vision": False, "risk": "high", "retry_policy": {}, "escalation_level": 0,
            "run_conditions": {"command": ["python", "-m", "card_condition.fake"], "code_sha": head, "seed": seed,
                               "config": {"plan": {"fake": mode, "reference_result": "r.json"}}, "hypothesis_id": "H-" + mode,
                               "description": {"hypothesis": "가설", "change": "변수 하나", "success_criterion": "fn<=1",
                                               "failure_criterion": "fn>1"}}}


def _state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class ExperimentRunTest(unittest.TestCase):
    def test_completed_experiment_is_charged_once_under_its_logical_key(self):
        root, src, head = _world(self)
        task = _task(head, "completed")
        key = queue.enqueue(root, task, NOW, source_root=src)
        summary = runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)
        self.assertEqual(summary["done"], [key], summary)
        [row] = events(root, path=budget.BUDGET)
        self.assertEqual((row["event"], row["data"]["key"], row["data"]["amount"]), ("charge", dedupe.logical_key(task), 1))
        with open(os.path.join(root, "tasks", key, "out", "record.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["status"], "completed")  # 어댑터가 해석한 기록의 사본
        self.assertEqual(runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)["executed"], 0)
        self.assertEqual(len(events(root, path=budget.BUDGET)), 1)

    def test_only_objective_non_execution_cancels_failed_and_unknown_keep_the_charge(self):
        root, src, head = _world(self)
        keys = {mode: queue.enqueue(root, _task(head, mode), NOW, source_root=src)
                for mode in ("busy", "setup", "failed", "quiet_fail", "setup_after_folder", "running")}
        summary = runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)
        charged = {r["data"]["key"]: r["seq"] for r in events(root, "charge", budget.BUDGET)}
        cancelled = {r["data"]["key"] for r in events(root, "cancel", budget.BUDGET)}
        logical = {mode: dedupe.logical_key(_task(head, mode)) for mode in keys}
        self.assertEqual(set(charged), set(logical.values()))  # 실행 시작마다 한 번
        self.assertEqual(cancelled, {logical["busy"], logical["setup"]})  # 안내문 + 새 실험 폴더 없음 = 실행 안 됨
        self.assertEqual(budget.usage(root, "experiment", budget.period_of("experiment", NOW)), 4)
        for mode in ("busy", "setup", "failed"):
            self.assertEqual(_state(root, keys[mode]), states.FAILED, mode)
        for mode in ("quiet_fail", "setup_after_folder", "running"):  # 결과 불명: 작업권을 남겨 확인 대기(자동 재실행 안 함)
            self.assertEqual(_state(root, keys[mode]), states.INTERRUPTED, (mode, summary))
        extra = queue.enqueue(root, _task(head, "completed", seed=2), NOW, source_root=src)
        with open(os.path.join(src, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("# 등록 뒤 추적 파일 변경\n")  # 실행 직전 대조 실패: executor를 부르지 않는다 = 실행 안 됨
        before = open(os.path.join(src, "artifacts", "argv.log"), encoding="utf-8").read()
        runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)
        self.assertEqual(_state(root, extra), states.FAILED)
        self.assertEqual(open(os.path.join(src, "artifacts", "argv.log"), encoding="utf-8").read(), before)
        self.assertIn(dedupe.logical_key(_task(head, "completed", seed=2)), {r["data"]["key"] for r in events(root, "cancel", budget.BUDGET)})
        self.assertEqual(budget.usage(root, "experiment", budget.period_of("experiment", NOW)), 4)

    def test_refused_or_halted_budget_runs_nothing_and_returns_the_task(self):
        root, src, head = _world(self)
        for i in range(20):
            budget.charge(root, "experiment", 1, NOW, key="other-%d" % i)
        key = queue.enqueue(root, _task(head, "completed"), NOW, source_root=src)
        summary = runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)
        self.assertEqual(summary["stopped"], {key: "budget_refused:limit"})
        self.assertFalse(os.path.exists(os.path.join(src, "artifacts", "argv.log")))  # 실행하지 않았다
        self.assertEqual((_state(root, key), os.path.exists(os.path.join(root, "tasks", key, "lease.json"))), (states.PENDING, False))
        self.assertIn(opstate.BUDGET_EXCEEDED, opstate.load(root)["conditions"])
        root2, src2, head2 = _world(self)
        key2 = queue.enqueue(root2, _task(head2, "completed"), NOW, source_root=src2)
        opstate.set_condition(root2, opstate.USER_STOPPED, NOW, "user", "중단")
        self.assertEqual(runner.drain(root2, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src2)["stopped"],
                         {key2: "budget_refused:halted:USER_STOPPED"})
        with open(os.path.join(root2, opstate.OPSTATE), "w", encoding="utf-8") as handle:
            handle.write("ORIG")  # 깨진 운영 상태 = INTEGRITY_HALT: 실험을 시작하지 않는다
        self.assertEqual(runner.drain(root2, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src2)["stopped"],
                         {key2: "budget_refused:halted:INTEGRITY_HALT"})
        root3, src3, head3 = _world(self)
        key3 = queue.enqueue(root3, _task(head3, "completed"), NOW, source_root=src3)
        budget.charge(root3, "experiment", 1, NOW, key="x")
        with open(os.path.join(root3, budget.BUDGET), "a", encoding="utf-8") as handle:
            handle.write('{"seq": 1, "ev')  # 반쯤 쓴 장부 줄: 사용량을 모르므로 실행하지 않고 무결성 정지(종료 코드 3)
        summary = runner.drain(root3, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src3)
        self.assertTrue(summary["integrity"].startswith("INTEGRITY: budget"), summary)
        self.assertEqual((_state(root3, key3), os.path.exists(os.path.join(src3, "artifacts", "argv.log"))), (states.PENDING, False))
        for r, s in ((root, src), (root2, src2)):
            self.assertFalse(os.path.exists(os.path.join(s, "artifacts", "argv.log")), r)

    def test_registration_and_call_depth(self):
        self.assertEqual(experiment_exec.EXECUTORS, {"experiment": experiment_exec.execute})
        error = experiment_exec.ExperimentError("deterministic", {"status": "not_started"})
        self.assertEqual((error.status, experiment_exec.ExperimentError("interrupted").status), ("not_started", None))
        graph = kit.call_graph()
        for name in ("runner.main", "experiment_exec.execute"):
            depth, path = kit.longest(name, graph)
            self.assertLessEqual(depth, 4, path)


if __name__ == "__main__":
    unittest.main()
