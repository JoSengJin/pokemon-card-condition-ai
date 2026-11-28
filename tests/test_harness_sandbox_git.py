"""봉인 자료의 git 우회 차단(합성 git 저장소, 실제 sandbox-exec 하위 프로세스): sandbox 프로필은 저장소·HARNESS_SOURCE_ROOT의 git 폴더
(일반 저장소의 .git 폴더, worktree면 .git 파일이 가리키는 git 폴더와 공통 git 폴더 commondir) 읽기를 거절한다.

- 2026-11-28 독립 검증 재현: sandbox 안에서 `git -C <src> show HEAD:vault/a.json`이 봉인 파일 내용을 출력했다(.git을 막지 않음).
- git show와 .git 객체 파일 직접 읽기를 둘 다 시험한다. 정상 파일 읽기는 그대로 된다. 저장소는 시험이 임시 폴더에 만든다(네트워크 없음).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from harness import claude_perm, sandbox
from harness import contract as ct
from harness.experiment_exec import SOURCE_ENV
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_sandbox_git:EXECUTORS"
SECRET = "SYNTHETIC-SEALED-7q"


def gitpeek(task, out_dir):
    """sandbox 안 executor: git show·git 폴더 직접 읽기·정상 읽기를 시도해 결과를 result.txt에 쓴다(내용이 보이면 leaked)."""
    got, where = {}, task["inputs"]
    for name in ("main", "wt"):
        shown = subprocess.run(["/usr/bin/git", "-C", where[name], "show", "HEAD:vault/a.json"], capture_output=True, text=True)
        got["show_" + name] = "leaked" if SECRET in shown.stdout else "denied"
    for name, path in (("object", where["object"]), ("head", os.path.join(where["main"], ".git", "HEAD")),
                       ("wt_gitdir_head", where["wt_gitdir_head"]), ("open_ok", os.path.join(where["wt"], "open", "ok.json"))):
        try:
            with open(path, "rb") as handle:
                handle.read()
            got[name] = "ok"
        except OSError as exc:
            got[name] = "denied:%d" % exc.errno
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        json.dump(got, handle)
    return ["result.txt"]


EXECUTORS = {"gitpeek": gitpeek}


def git_repo(test):
    """임시 git 저장소 main(vault/a.json = SECRET 커밋)과 그 worktree wt. 목록은 ["vault"]. 실행기에 넘길 경로 dict와 base."""
    base = os.path.realpath(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, base, True)
    main, wt = os.path.join(base, "main"), os.path.join(base, "wt")
    for rel, text in (("vault/a.json", SECRET), ("open/ok.json", "{}")):
        os.makedirs(os.path.dirname(os.path.join(main, rel)), exist_ok=True)
        with open(os.path.join(main, rel), "w") as handle:
            handle.write(text)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=/dev/null", "-C", main]
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "m"], ["worktree", "add", "-q", wt]):
        subprocess.run(git + args, check=True, capture_output=True)
    blob = subprocess.run(git + ["rev-parse", "HEAD:vault/a.json"], check=True, capture_output=True, text=True).stdout.strip()
    listing = os.path.join(base, "list.json")
    with open(listing, "w") as handle:
        handle.write('{"paths": ["vault"]}')
    patcher = mock.patch.object(claude_perm, "SEALED_LIST", listing)
    patcher.start()
    test.addCleanup(patcher.stop)
    return base, {"main": main, "wt": wt, "object": os.path.join(main, ".git", "objects", blob[:2], blob[2:]),
                  "wt_gitdir_head": os.path.join(main, ".git", "worktrees", "wt", "HEAD")}


class SandboxGitTest(unittest.TestCase):
    def test_git_show_and_direct_git_reads_are_refused_for_plain_repo_and_worktree(self):
        base, where = git_repo(self)
        self.assertTrue(os.path.isfile(os.path.join(where["wt"], ".git")))  # worktree의 .git은 파일이다
        expect = {"show_main": "denied", "show_wt": "denied", "object": "denied:1", "head": "denied:1", "wt_gitdir_head": "denied:1",
                  "open_ok": "ok"}
        for source in ("main", "wt"):  # main: .git 폴더 분기, wt: .git 파일 → gitdir·commondir 분기
            with mock.patch.dict(os.environ, {SOURCE_ENV: where[source]}):
                task = make_contract("G" + source, task_type="gitpeek", inputs=where)
                final = os.path.join(base, "root", "tasks", ct.task_key(task), "out")
                self.assertEqual(sandbox.run_one(os.path.join(base, "root"), SPEC, "gitpeek", task, final), ["result.txt"])
                with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle), expect, source)

    def test_unknown_dot_git_file_fails_closed(self):
        base, where = git_repo(self)
        with open(os.path.join(where["wt"], ".git"), "w") as handle:
            handle.write("not a gitdir line\n")
        with self.assertRaises(ValueError):
            claude_perm.sealed_paths([where["wt"]])


if __name__ == "__main__":
    unittest.main()
