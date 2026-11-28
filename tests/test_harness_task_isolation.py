"""2차 결함 G5·G11·변이 N17·N20: 한 작업·한 선언의 문제로 Supervisor 전체를 멈추지 않는다(INTEGRITY_HALT는 장부·상태 무결성만).

- 선언 그래프의 계약 하나가 거절되면(입력 SHA가 실제 파일과 다름 등) 그 선언만 등록하지 않고 장부·알림(declaration_rejected)을 한 번 남긴다.
  선언 파일 자체가 깨졌거나 순환이면 그 회차의 그래프 등록만 건너뛰고 알림을 한 번 남긴다. 독립 작업은 계속한다(G5·N20).
- Claude 완료 선언 자리가 폴더·링크면 그 작업만 대기한다(G11).
- 입력은 SHA가 맞아도 원본 폴더 밖(.. 경로)이면 등록·실행 모두 거절한다(N17).
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import claude_job, opstate, queue, runner, states, supervisor
from harness import contract as ct
from harness.jsonio import write_json
from tests.test_harness_git_kit import CODE, git_source
from tests.test_harness_runner_kit import WRAPPED_RUNNER, task
from tests.test_harness_supervisor_kit import events, llm_task, make_fake, runs

EXEC = "tests.test_harness_executors:EXECUTORS"


def _state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


def _experiment(src, rel="data/a.json", text=b"v1"):
    """src 아래 rel을 쓰고 그 SHA로 만든 실험 계약(입력 자리표시자 포함). src는 git 저장소, code_sha는 그 HEAD(3차 결함 H1)."""
    git_source(src)
    os.makedirs(os.path.dirname(os.path.join(src, os.path.normpath(rel))), exist_ok=True)
    with open(os.path.join(src, os.path.normpath(rel)), "wb") as handle:
        handle.write(text)
    return {"task_type": "experiment", "inputs": {rel: hashlib.sha256(text).hexdigest()}, "outputs": ["m.json"], "depends_on": [],
            "needs_llm": False, "needs_vision": False, "risk": "low", "retry_policy": {}, "escalation_level": 0,
            "run_conditions": {"command": ["python", "t.py", "{input:%s}" % rel], "code_sha": CODE,
                               "input_roles": {rel: "data"}}}


class TaskIsolationTest(unittest.TestCase):
    def _supervise(self, root, text, src=None):
        """선언 파일을 text 그대로 쓰고 독립 Python 작업 하나와 함께 Supervisor를 3회차 돌린다. (독립 작업 키, 요약)."""
        src, marks = src or tempfile.mkdtemp(), tempfile.mkdtemp()
        for path in (src, marks):
            self.addCleanup(shutil.rmtree, path, True)
        indep = queue.enqueue(root, task("I"), 1.0)
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        with open(os.path.join(root, supervisor.DECLARED), "w", encoding="utf-8") as handle:
            handle.write(text)
        with mock.patch.object(supervisor, "RUNNER", WRAPPED_RUNNER), mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks}):
            out = supervisor.run(root, executors=EXEC, max_cycles=3, poll_s=0, source_root=src)
        self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT, text)
        self.assertEqual(_state(root, indep), states.VERIFIED, text)  # 독립 작업은 계속한다
        return [e["data"] for e in events(root, path=opstate.NOTIFICATIONS)]

    def test_one_rejected_declaration_does_not_halt_and_is_notified_once(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        exp = _experiment(src)
        with open(os.path.join(src, "data", "a.json"), "wb") as handle:  # 선언 뒤 원본 자료가 바뀌었다(정상 작업일 수 있다)
            handle.write(b"v2")
        notes = self._supervise(root, json.dumps({ct.task_key(exp): exp}), src)
        self.assertFalse(os.path.isdir(os.path.join(root, "tasks", ct.task_key(exp))))
        self.assertEqual([n["kind"] for n in notes], ["declaration_rejected"])  # 회차마다 다시 알리지 않는다
        self.assertIn("SHA", json.dumps(notes[0], ensure_ascii=False))
        self.assertEqual(len(events(root, "declaration_rejected")), 1)

    def test_broken_or_mismatched_declaration_file_skips_only_graph_registration(self):
        a = dict(task("A"), depends_on=["b" * 64])
        mismatched = {ct.task_key(a): a, "b" * 64: dict(task("B"), depends_on=[ct.task_key(a)])}  # 키와 계약 해시가 다름
        for text in ("{not json", json.dumps(["not", "a", "dict"]), json.dumps(mismatched)):
            root = tempfile.mkdtemp()
            notes = self._supervise(root, text)
            self.assertEqual([n["kind"] for n in notes], ["declaration_rejected"], text)
            self.assertFalse(os.path.isdir(os.path.join(root, "tasks", ct.task_key(a))), text)  # 의존이 거절된 작업은 등록 대기

    def test_declaration_path_that_is_a_folder_holds_only_that_task(self):
        root = tempfile.mkdtemp()
        bad, good = llm_task(root, "a"), llm_task(root, "b")
        os.makedirs(os.path.join(root, "tasks", bad, "out", ct.DECLARATION, "x"))
        claude, log, env = make_fake(self, [{"do": "success"}] * 3)
        out = supervisor.run(root, claude_bin=claude, max_cycles=4, poll_s=0, env=env)
        self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT)
        self.assertEqual((_state(root, bad), _state(root, good), len(runs(log))), (states.PENDING, states.VERIFIED, 1))
        with open(claude_job.paths(root, bad)[0], encoding="utf-8") as handle:
            job = json.load(handle)
        self.assertEqual(job["status"], "blocked")
        self.assertIn("declaration_path", job["hold_reason"])

    def test_inputs_outside_the_source_folder_are_refused_even_with_a_matching_sha(self):
        base, root = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        src = os.path.join(base, "src")
        outside = _experiment(src, rel="../outside/a.json")  # base/outside/a.json: SHA는 실제 파일과 같다
        with self.assertRaises(ct.ContractError):
            queue.enqueue(root, outside, 1.0, source_root=src)
        key = ct.task_key(outside)  # 옛 규칙으로 이미 들어온 계약이라고 가정: 실행 직전 입력 복사도 같은 규칙으로 거절한다
        write_json(os.path.join(root, "tasks", key, "contract.json"), outside)
        executor = mock.Mock(return_value=["m.json"])
        summary = runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)
        self.assertEqual((executor.call_count, summary["failed"]), (0, [[key, "deterministic"]]))

if __name__ == "__main__":
    unittest.main()
