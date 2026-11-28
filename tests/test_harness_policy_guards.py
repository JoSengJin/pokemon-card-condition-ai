"""2단계 보조 규칙: 예산 멱등 키, 그래프 등록의 중복 거절, 실험 유형은 등록해도 자동 재실행 금지, 결과 확인 대기는 장부·알림 한 번,
이미 완료한 작업은 다시 반영하지 않음."""
import hashlib
import os
import tempfile
import unittest
from unittest import mock

from harness import budget, graph, opstate, queue, recovery
from harness import contract as ct
from tests.test_harness_git_kit import CODE, git_source
from tests.test_harness_support import BOOT, claim, dead_lease, finish, make_contract
from tests.test_harness_supervisor_kit import events

T0 = 1_800_000_000.0


def experiment(src, seed=1, **extra):
    """src에 입력 data/a.json을 쓰고 그 SHA로 만든 실험 계약(검증 결함 F3: 입력은 실제 파일과 대조하고 입력마다 역할을 적는다).
    src는 git 저장소로 만들고 code_sha는 그 HEAD다(3차 결함 H1)."""
    git_source(src)
    os.makedirs(os.path.join(src, "data"), exist_ok=True)
    with open(os.path.join(src, "data", "a.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    task = dict(make_contract("e", task_type="experiment", inputs={"data/a.json": hashlib.sha256(b"{}").hexdigest()}), **extra)
    task["run_conditions"] = {"command": ["python", "train.py", "{input:data/a.json}"], "code_sha": CODE, "seed": seed,
                              "input_roles": {"data/a.json": "data"}}  # 입력은 자리표시자로 참조한다(2차 결함 G4)
    return task


class PolicyGuardTest(unittest.TestCase):
    def test_budget_charge_with_the_same_key_is_counted_once(self):
        root = tempfile.mkdtemp()
        first = budget.charge(root, "vision_zone", 10, T0, key="task-1:run-a")
        again = budget.charge(root, "vision_zone", 10, T0 + 1, key="task-1:run-a")  # 같은 단계의 반영·복구
        resumed = budget.charge(root, "vision_zone", 10, T0 + 2, key="task-1:run-b")  # 재개로 실제 사용이 더 생김
        self.assertEqual((first["used"], again["used"], again.get("already"), resumed["used"]), (10, 10, True, 20))
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 2)
        with self.assertRaises(budget.BudgetError):
            budget.charge(root, "vision_zone", 1, T0, key="")
        opstate.set_condition(root, opstate.USER_STOPPED, T0, "user", "중단")
        self.assertFalse(budget.charge(root, "vision_zone", 1, T0, key="task-1:run-a")["ok"])  # 정지 중에는 키가 있어도 거절

    def test_graph_registration_refuses_logical_duplicates(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        known = queue.enqueue(root, experiment(src), T0, source_root=src)
        twin, other = experiment(src, risk="high"), experiment(src, seed=7)
        declared = {ct.task_key(twin): twin, ct.task_key(other): other}
        got = graph.register_missing(root, declared, T0, source_root=src)
        self.assertEqual((got["registered"], got["duplicates"]), ([ct.task_key(other)], {ct.task_key(twin): known}))
        self.assertFalse(os.path.exists(os.path.join(root, "tasks", ct.task_key(twin))))
        with self.assertRaises(ct.ContractError):  # 판별할 수 없는 실행 조건(설명인지 조건인지 모르는 키)
            queue.enqueue(root, dict(experiment(src), run_conditions={"command": ["x"], "code_sha": "c" * 40, "lr": 1}), T0,
                          source_root=src)

    def test_experiment_is_never_auto_rerun_even_if_registered_and_waits_once(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        key = queue.enqueue(root, experiment(src), T0, source_root=src)
        dead_lease(root, key, T0, run_id="ab12")
        with mock.patch.object(recovery, "RERUN_SAFE_TYPES", frozenset({"experiment"})):
            plans = [claim(root, key, os.getpid(), BOOT, T0 + 7200 + i) for i in range(3)]
        self.assertEqual([(p["ok"], p["reason"]) for p in plans], [(False, "await_result")] * 3)
        [record] = [e["data"] for e in events(root, "awaiting_result")]  # 같은 대기는 한 번만 기록
        self.assertEqual((record["reason"], record["cause"], record["outcome"]), ("interrupted", "unknown", "unknown"))
        notes = [e["data"]["kind"] for e in events(root, path=opstate.NOTIFICATIONS)]
        self.assertEqual(notes, ["task_awaiting_result"])

    def test_completed_task_is_not_completed_again(self):
        root = tempfile.mkdtemp()
        key, run_id = finish(root, make_contract("c"), T0)
        self.assertEqual(claim(root, key, os.getpid(), BOOT, T0 + 5)["reason"], "skip")
        handle = queue.lease.lock(os.path.join(root, "tasks", key, "lease.json"))
        queue.lease.stamp(handle, os.getpid(), BOOT, T0, {"run_id": run_id})
        with self.assertRaises(queue.QueueError):  # done.json이 있으면 반영을 거절한다
            queue.complete(root, key, run_id, handle, T0 + 6)
        queue.lease.release(handle, remove=True)
        self.assertEqual(len(events(root, "completed")), 1)


if __name__ == "__main__":
    unittest.main()
