"""의존 그래프 대조 시험(T-dep): 빠진 작업 자동 등록, 순환 거절. 합성 시험이며 모델 성능 근거가 아니다."""
import os
import tempfile
import unittest

from harness import contract, graph, lease, queue, states
from tests.test_harness_support import BOOT, claim, alive_with, finish, make_contract

T0 = 1_000_000.0


def declare(*tasks):
    return {contract.task_key(t): t for t in tasks}


class GraphTest(unittest.TestCase):
    def test_verified_dependency_registers_the_missing_task_once(self):
        with tempfile.TemporaryDirectory() as root:
            first = make_contract(tag="a")
            key_a, _ = finish(root, first, T0)
            second = make_contract(tag="b", depends_on=[key_a])
            third = make_contract(tag="c", depends_on=[contract.task_key(second)])
            declared = declare(first, second, third)
            result = graph.register_missing(root, declared, T0 + 5, alive_with())
            key_b = contract.task_key(second)
            self.assertEqual(result, {"eligible": [key_b], "registered": [key_b]})  # c는 b가 VERIFIED가 아니라 대기
            self.assertEqual(states.classify(os.path.join(root, "tasks", key_b), T0, alive_with()), states.PENDING)
            self.assertEqual(graph.register_missing(root, declared, T0 + 6, alive_with()),
                             {"eligible": [], "registered": []})  # 멱등: 이미 대기 중

    def test_unverified_or_running_dependency_blocks_registration(self):
        with tempfile.TemporaryDirectory() as root:
            first = make_contract(tag="a")
            key_a = queue.enqueue(root, first, T0)  # PENDING
            second = make_contract(tag="b", depends_on=[key_a])
            declared = declare(first, second)
            self.assertEqual(graph.register_missing(root, declared, T0, alive_with()),
                             {"eligible": [], "registered": []})
            res = claim(root, key_a, os.getpid(), BOOT, T0)
            self.assertEqual(graph.register_missing(root, declared, T0, alive_with())["registered"], [])
            lease.release(res["lease"])

    def test_circular_dependencies_are_rejected(self):
        for graph_def in ({"a": ["b"], "b": ["a"]}, {"a": ["a"]}, {"a": ["b"], "b": ["c"], "c": ["a"]}):
            declared = {k: {"depends_on": deps} for k, deps in graph_def.items()}
            with self.subTest(graph_def), self.assertRaises(graph.GraphError):
                graph.reconcile(declared, lambda key: states.UNREGISTERED)
        diamond = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]}
        verified = {"a": states.VERIFIED, "b": states.VERIFIED, "c": states.PENDING, "d": states.UNREGISTERED}
        got = graph.reconcile({k: {"depends_on": d} for k, d in diamond.items()}, verified.get)
        self.assertEqual(got, [])  # 순환이 아닌 마름모는 통과, d는 c가 VERIFIED가 아니라 대기

    def test_states_other_than_verified_running_pending_are_eligible_but_not_re_registered(self):
        tasks = {"x": [], "f": ["x"], "i": ["x"], "c": ["x"], "v": ["x"], "r": ["x"], "p": ["x"], "u": ["x"]}
        state = {"x": states.VERIFIED, "f": states.FAILED, "i": states.INTERRUPTED, "c": states.CORRUPT,
                 "v": states.VERIFIED, "r": states.RUNNING, "p": states.PENDING, "u": states.UNREGISTERED}
        got = graph.reconcile({k: {"depends_on": d} for k, d in tasks.items()}, state.get)
        self.assertEqual(got, ["f", "i", "c", "u"])
        with tempfile.TemporaryDirectory() as root:
            first = make_contract(tag="a")
            key_a, _ = finish(root, first, T0)
            failing = make_contract(tag="f", depends_on=[key_a])
            key_f = queue.enqueue(root, failing, T0)
            res = claim(root, key_f, os.getpid(), BOOT, T0)
            queue.fail(root, key_f, res["run_id"], res["lease"], "deterministic", "TypeError", T0)
            result = graph.register_missing(root, declare(first, failing), T0 + 1, alive_with())
            self.assertEqual(result, {"eligible": [key_f], "registered": []})  # 실패 정책은 claim/recover가 판단

    def test_declared_key_must_match_the_contract_hash(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(graph.GraphError):
                graph.register_missing(root, {"0" * 64: make_contract()}, T0, alive_with())

    def test_register_missing_validates_each_contract_before_writing_it(self):
        with tempfile.TemporaryDirectory() as root:
            invalid = make_contract(outputs=[])  # 키는 계약 해시와 맞지만 계약 자체가 규칙 위반
            with self.assertRaises(contract.ContractError):
                graph.register_missing(root, {contract.task_key(invalid): invalid}, T0, alive_with())
            self.assertFalse(os.path.exists(os.path.join(root, "tasks", contract.task_key(invalid))))
