"""3차 결함 H1: 실험·학습·평가의 run_conditions.code_sha는 형식만이 아니라 source_root의 실제 코드와 대조한다.

- 등록(queue.enqueue·graph.register_missing)과 executor 실행 직전(runner._execute) 모두 code_sha가 source_root의 `git rev-parse HEAD`와 같고
  작업 트리에 추적 파일 변경이 없어야 통과한다. 다른 16진·길이만 다른 값(40 ↔ 64자)·git 저장소가 아님·저장소의 하위 폴더·추적 파일 변경은
  거절(fail-closed, 그 작업만). 대소문자만 다른 HEAD는 같은 코드다(키에는 정규화한 HEAD).
- needs_llm=false인 실험·학습·평가는 needs_vision=true를 거절하고 키에서 needs_vision을 뺀다(실행에 쓰이지 않는 값으로 다시 등록하는 우회).
"""
import hashlib
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import contract as ct
from harness import dedupe, graph, queue, runner, states
from tests.test_harness_git_kit import CODE, git, git_source
from tests.test_harness_support import make_contract

T0 = 1_800_000_000.0


def _experiment(src, code_sha=CODE, tag="0", **extra):
    """src에 추적하지 않는 입력 data/a.json을 쓰고 그 SHA로 만든 실험 계약(tag: 명령에 넣는 사례 표시, 키를 사례마다 다르게)."""
    os.makedirs(os.path.join(src, "data"), exist_ok=True)
    with open(os.path.join(src, "data", "a.json"), "wb") as handle:
        handle.write(b"rows")
    task = dict(make_contract("c", task_type="experiment", inputs={"data/a.json": hashlib.sha256(b"rows").hexdigest()}), **extra)
    task["run_conditions"] = {"command": ["python", "train.py", "--tag", tag, "{input:data/a.json}"], "code_sha": code_sha}
    return task


class CodeShaTest(unittest.TestCase):
    def _src(self, repo=True):
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        if repo:
            self.assertEqual(git_source(src), CODE)
        return src

    def test_code_sha_must_be_the_clean_head_of_the_source_folder(self):
        root, src = tempfile.mkdtemp(), self._src()
        first = queue.enqueue(root, _experiment(src), T0, source_root=src)
        with self.assertRaises(queue.DuplicateTask) as caught:  # 대소문자만 다른 HEAD = 같은 코드
            queue.enqueue(root, _experiment(src, code_sha=CODE.upper(), risk="high"), T0, source_root=src)
        self.assertEqual(caught.exception.existing, first)
        dirty = self._src()
        with open(os.path.join(dirty, "code.py"), "a", encoding="utf-8") as handle:
            handle.write("CHANGED = 1\n")
        sub = os.path.join(self._src(), "sub")
        os.makedirs(sub)
        bad = [(src, "d" * 40), (src, CODE + "0" * 24), (src, CODE[:-1] + ("0" if CODE[-1] != "0" else "1")),
               (self._src(repo=False), CODE), (dirty, CODE), (sub, CODE)]
        for index, (where, sha) in enumerate(bad):
            task = _experiment(where, code_sha=sha, tag="case-%d" % index)
            with self.assertRaises(ct.ContractError, msg=(where, sha)):
                queue.enqueue(root, task, T0, source_root=where)
            got = graph.register_missing(root, {ct.task_key(task): task}, T0, source_root=where)
            self.assertIn("code_sha", got["rejected"][ct.task_key(task)], (where, sha))
        self.assertEqual(os.listdir(os.path.join(root, "tasks")), [first])

    def test_needs_vision_is_refused_for_non_llm_experiments_and_left_out_of_the_key(self):
        root, src = tempfile.mkdtemp(), self._src()
        with self.assertRaises(ct.ContractError):
            queue.enqueue(root, _experiment(src, needs_vision=True), T0, source_root=src)
        task = _experiment(src)
        self.assertEqual(dedupe.logical_key(task), dedupe.logical_key({k: v for k, v in task.items() if k != "needs_vision"}))
        self.assertFalse(os.path.isdir(os.path.join(root, "tasks")))

    def test_code_changed_after_registration_is_refused_right_before_execution(self):
        for change in ("commit", "dirty"):
            root, src = tempfile.mkdtemp(), self._src()
            key = queue.enqueue(root, _experiment(src), T0, source_root=src)
            with open(os.path.join(src, "code.py"), "a", encoding="utf-8") as handle:
                handle.write("CHANGED = 1\n")
            if change == "commit":
                git(src, "commit", "-q", "-am", "next")
            executor = mock.Mock(return_value=["result.txt"])
            summary = runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)
            self.assertEqual((executor.call_count, summary["failed"][0][1]), (0, "deterministic"), change)
            task_dir = os.path.join(root, "tasks", key)
            self.assertEqual(states.state_of(states.facts(task_dir), False), states.FAILED, change)
            self.assertIn("code_sha", states.failures(task_dir)[0]["error"], change)

    def test_executor_gets_the_command_with_placeholders_replaced_by_the_verified_copy(self):
        root, src = tempfile.mkdtemp(), self._src()
        key = queue.enqueue(root, _experiment(src), T0, source_root=src)
        seen = []

        def executor(task, out_dir):  # 3차 결함 H7: runner가 자리표시자를 입력 사본(작업 폴더 in/) 절대 경로로 바꾼 명령을 넘긴다
            with open(task["run_conditions"]["command"][-1], "rb") as handle:
                seen.append((task["run_conditions"]["command"], handle.read()))
            with open(os.path.join(out_dir, "result.txt"), "w", encoding="utf-8") as handle:
                handle.write("ok")
            return ["result.txt"]
        self.assertEqual(runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)["done"], [key])
        copy = os.path.join(os.path.abspath(root), "tasks", key, "in", "data", "a.json")
        self.assertEqual(seen, [(["python", "train.py", "--tag", "0", copy], b"rows")])
        with open(os.path.join(root, "tasks", key, "contract.json"), encoding="utf-8") as handle:
            self.assertIn("{input:data/a.json}", handle.read())  # 계약 자체는 그대로


if __name__ == "__main__":
    unittest.main()
