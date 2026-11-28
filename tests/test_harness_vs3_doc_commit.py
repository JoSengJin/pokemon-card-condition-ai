"""VS3 필수 합성 시험 9(5차 검증 P1): 문서 커밋만 변경된 동일 실험의 중복 실행 차단.

- 논리 키의 코드 자리는 `docs/` 아래 `.md` 일반 파일을 뺀 추적 파일 목록의 지문이다. 그 파일만 바꾼 커밋 뒤 같은 실험은 중복(DuplicateTask)이고
  executor가 다시 불리지 않는다.
- 반례(합쳐지면 안 되는 것): 코드(.py)·설정(docs 아래 .json 포함)·루트 .md(AGENTS.md는 코드가 읽는다)·docs .md 링크(대상이 바뀜)·
  명령이 이름으로 가리키는 docs .md·config 글자에 .md가 든 실험은 다른 실험이다.
"""
import os
import shutil
import tempfile
import unittest

from harness import queue, runner
from tests.test_harness_code_sha import _experiment
from tests.test_harness_git_kit import git, git_source

T0 = 1_800_000_000.0


def _commit(src, rel, text, link=None):
    """src에 rel을 쓰고(link면 그 이름을 가리키는 심볼릭 링크) 커밋한 뒤 HEAD를 돌려준다."""
    path = os.path.join(src, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if link:
        if os.path.lexists(path):
            os.remove(path)
        os.symlink(link, path)
    else:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    git(src, "add", "-A", rel)
    git(src, "commit", "-q", "-m", "edit " + rel)
    return git(src, "rev-parse", "HEAD")


class DocCommitTest(unittest.TestCase):
    def _world(self):
        root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
        for path in (root, src):
            self.addCleanup(shutil.rmtree, path, True)
        git_source(src)
        _commit(src, "docs/notes.md", "v1\n")
        _commit(src, "docs/target.md", "t1\n")
        _commit(src, "docs/link.md", None, link="target.md")
        _commit(src, "AGENTS.md", "rules v1\n")
        return root, src

    def test_docs_only_commit_after_a_finished_experiment_is_a_duplicate_and_does_not_run_again(self):
        root, src = self._world()
        calls = []
        first = queue.enqueue(root, _experiment(src, code_sha=git(src, "rev-parse", "HEAD")), T0, source_root=src)
        runner.drain(root, {"experiment": lambda task, out: calls.append(1) or open(os.path.join(out, "result.txt"), "w").close()
                            or ["result.txt"]}, source_root=src)
        for rel in ("docs/notes.md", "docs/collaboration/tasks/new-task.md"):  # 문서 수정·새 문서
            head = _commit(src, rel, "docs only %s\n" % rel)
            with self.assertRaises(queue.DuplicateTask, msg=rel) as caught:
                queue.enqueue(root, _experiment(src, code_sha=head, risk="r-" + rel), T0, source_root=src)
            self.assertEqual(caught.exception.existing, first)
        self.assertEqual(len(calls), 1)  # 같은 실험은 한 번만 실행됐다

    def test_code_config_root_markdown_and_doc_links_are_not_merged_into_the_same_experiment(self):
        root, src = self._world()
        queue.enqueue(root, _experiment(src, code_sha=git(src, "rev-parse", "HEAD")), T0, source_root=src)
        cases = [("code.py", "CODE = 2\n", None), ("docs/config.json", "{\"lr\": 2}\n", None), ("AGENTS.md", "rules v2\n", None),
                 ("README.md", "readme\n", None), ("docs/link.md", None, "notes.md"), ("docs/sub.md/x.py", "X = 1\n", None)]
        for index, (rel, text, link) in enumerate(cases):
            head = _commit(src, rel, text, link)
            queue.enqueue(root, _experiment(src, code_sha=head, risk="c%d" % index), T0, source_root=src)  # 중복이 아니다(새 키)

    def test_docs_markdown_named_by_the_command_or_config_is_part_of_the_experiment(self):
        root, src = self._world()
        for index, where in enumerate(("command", "config")):
            task = _experiment(src, code_sha=git(src, "rev-parse", "HEAD"), tag="named-%d" % index)
            if where == "command":
                task["run_conditions"]["command"].insert(2, "docs/notes.md")
            else:
                task["run_conditions"]["config"] = {"rules": "docs/notes.md"}
            queue.enqueue(root, task, T0, source_root=src)
            head = _commit(src, "docs/notes.md", "changed for %s\n" % where)
            again = dict(task, risk="again")
            again["run_conditions"] = dict(task["run_conditions"], code_sha=head)
            queue.enqueue(root, again, T0, source_root=src)  # 실험이 읽을 수 있는 문서가 바뀌었다: 다른 실험


if __name__ == "__main__":
    unittest.main()
