"""4차 결함 I4·I5·변이 V01: 실험·학습·평가의 코드 식별.

- 대조는 그대로 등록·실행 직전 source_root의 HEAD(커밋 SHA)로 하고, 논리 키의 코드 자리에는 HEAD^{tree}를 넣는다(I4). 그래서 빈 커밋·amend·
  같은 tree의 새 커밋(rebase와 같은 효과)만으로는 같은 실험이 새 키로 다시 등록되지 않는다. 코드가 실제로 바뀐 커밋은 새 키다.
- skip-worktree·assume-unchanged 표시가 있는 추적 파일이 있으면 작업 트리가 깨끗한지 판별할 수 없어 거절한다(I5, fail-closed). 실행 직전에도 같다.
- command 토큰(--opt=value의 값 포함) 중 source_root 안에 실제로 있는 파일인데 git이 추적하지 않는 것이 있으면 거절한다(I5: 커밋하지 않은 스크립트를
  같은 code_sha로 실행하는 경로). 자리표시자 입력·없는 파일·source_root 밖은 보지 않는다.
- 사용자 환경의 GIT_DIR·GIT_WORK_TREE가 다른 저장소를 가리켜도 source_root를 본다(V01).
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import contract as ct
from harness import graph, queue, runner, states
from tests.test_harness_code_sha import _experiment
from tests.test_harness_git_kit import CODE, git, git_source

T0 = 1_800_000_000.0


class CodeTreeTest(unittest.TestCase):
    def _src(self, text="CODE = 1\n"):
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src, text)
        return src

    def test_same_tree_after_empty_commit_amend_or_new_history_is_a_duplicate(self):
        root, src = tempfile.mkdtemp(), self._src()
        first = queue.enqueue(root, _experiment(src), T0, source_root=src)
        steps = [["commit", "-q", "--allow-empty", "-m", "docs only"], ["commit", "-q", "--amend", "--allow-empty", "-m", "reworded"]]
        for index, step in enumerate(steps + ["orphan"]):
            if step == "orphan":  # 같은 tree를 부모 없는 새 커밋으로(rebase처럼 이력만 바뀜)
                git(src, "reset", "-q", "--hard", git(src, "commit-tree", "HEAD^{tree}", "-m", "rewritten"))
            else:
                git(src, *step)
            head = git(src, "rev-parse", "HEAD")
            self.assertNotEqual(head, CODE)
            task = dict(_experiment(src, code_sha=head), risk="r%d" % index)
            with self.assertRaises(queue.DuplicateTask, msg=step) as caught:
                queue.enqueue(root, task, T0, source_root=src)
            self.assertEqual(caught.exception.existing, first)
            self.assertEqual(graph.register_missing(root, {ct.task_key(task): task}, T0, source_root=src)["duplicates"],
                             {ct.task_key(task): first}, step)
        with open(os.path.join(src, "code.py"), "a", encoding="utf-8") as handle:
            handle.write("CHANGED = 2\n")
        git(src, "commit", "-q", "-am", "real change")
        changed = queue.enqueue(root, _experiment(src, code_sha=git(src, "rev-parse", "HEAD")), T0, source_root=src)
        self.assertNotEqual(changed, first)  # 코드가 바뀐 커밋은 다른 실험

    def test_skip_worktree_or_assume_unchanged_files_are_refused_at_registration_and_before_execution(self):
        for flag in ("--skip-worktree", "--assume-unchanged"):
            root, src = tempfile.mkdtemp(), self._src()
            key = queue.enqueue(root, _experiment(src, tag="before"), T0, source_root=src)
            with open(os.path.join(src, "code.py"), "a", encoding="utf-8") as handle:
                handle.write("HIDDEN = 1\n")
            git(src, "update-index", flag, "code.py")
            self.assertEqual(git(src, "status", "--porcelain", "--untracked-files=no"), "")  # status만으로는 깨끗해 보인다
            task = _experiment(src, tag="after")
            with self.assertRaises(ct.ContractError, msg=flag):
                queue.enqueue(root, task, T0, source_root=src)
            self.assertIn("ContractError", graph.register_missing(root, {ct.task_key(task): task}, T0, source_root=src)["rejected"][
                ct.task_key(task)], flag)
            executor = mock.Mock(return_value=["result.txt"])
            summary = runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)
            self.assertEqual((executor.call_count, summary["failed"][0][1]), (0, "deterministic"), flag)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.FAILED, flag)

    def test_untracked_files_named_by_the_command_are_refused(self):
        root, src = tempfile.mkdtemp(), self._src()
        with open(os.path.join(src, "new_exp.py"), "w", encoding="utf-8") as handle:
            handle.write("print('not committed')\n")
        script = os.path.join(src, "new_exp.py")
        for index, cmd in enumerate([["python", "new_exp.py"], ["python", "./new_exp.py"], ["python", script], ["python", "--run=new_exp.py"],
                                     ["python", os.path.join(os.path.realpath(src), "x", "..", "new_exp.py")]]):
            task = _experiment(src, tag="u%d" % index)
            task["run_conditions"]["command"] = cmd + ["{input:data/a.json}"]
            with self.assertRaises(ct.ContractError, msg=cmd):
                queue.enqueue(root, task, T0, source_root=src)
        self.assertFalse(os.path.isdir(os.path.join(root, "tasks")))
        task = _experiment(src, tag="tracked")
        task["run_conditions"]["command"] = ["python", "code.py", "missing.py", "{input:data/a.json}"]  # 추적 파일·없는 파일은 통과
        queue.enqueue(root, task, T0, source_root=src)
        git(src, "add", "new_exp.py")
        git(src, "commit", "-q", "-m", "add script")
        task = _experiment(src, code_sha=git(src, "rev-parse", "HEAD"), tag="committed")
        task["run_conditions"]["command"] = ["python", "new_exp.py", "{input:data/a.json}"]
        queue.enqueue(root, task, T0, source_root=src)  # 커밋한 뒤에는 등록된다

    def test_user_git_environment_pointing_at_another_repository_is_ignored(self):
        root, src, other = tempfile.mkdtemp(), self._src(), self._src("OTHER = 1\n")
        theirs = git(other, "rev-parse", "HEAD")
        self.assertNotEqual(theirs, CODE)
        fake = {"GIT_DIR": os.path.join(other, ".git"), "GIT_WORK_TREE": src, "GIT_INDEX_FILE": os.path.join(other, ".git", "index")}
        with mock.patch.dict(os.environ, fake):
            with self.assertRaises(ct.ContractError):  # 다른 저장소의 HEAD를 code_sha로 적어도 source_root의 HEAD와 대조한다
                queue.enqueue(root, _experiment(src, code_sha=theirs, tag="theirs"), T0, source_root=src)
            key = queue.enqueue(root, _experiment(src, tag="ours"), T0, source_root=src)
            executor = mock.Mock(return_value=["result.txt"])
            runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)
        self.assertEqual(executor.call_count, 1)  # 실행 직전 대조도 source_root(같은 HEAD)를 본다
        self.assertTrue(os.path.isdir(os.path.join(root, "tasks", key)))


if __name__ == "__main__":
    unittest.main()
