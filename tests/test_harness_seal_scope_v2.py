"""D4 독립 검증 결함 수정 시험(F1~F4 + 대화 기록 폴더): 조상 루트 차단, stage_inputs의 저장소 밖 루트 거절, 실행 중 생긴 glob 파일 차단(SBPL regex),
available·sandboxed의 source_root 기준 계산. 임시 git 저장소·가짜 목록만 쓴다. 대화 기록 폴더는 stat만 확인한다(내용·이름 목록 열람 없음).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from harness import claude_perm, runner, sandbox
from harness.cas import sha_file
from tests.test_harness_seal_scope import GIT, git_world, sandboxed

SPEC = "tests.test_harness_sandbox_read:EXECUTORS"
LATE = ("import sys, time\ntime.sleep(2)\nfor p in sys.argv[1:]:\n"
        "    try:\n        print(open(p).read())\n    except OSError as exc:\n        print(exc.errno)\n")


class SealScopeV2Test(unittest.TestCase):
    def test_f1_a_root_that_is_an_ancestor_of_the_repo_or_source_root_stops_execution(self):
        w = git_world(self)
        open(claude_perm.OUTSIDE_LIST, "w").write(json.dumps({"roots": [w["base"]]}))  # 목록 루트가 저장소의 조상
        with self.assertRaises(ValueError):
            claude_perm.outside_roots([w["repo"]])
        with self.assertRaises(ValueError):  # source_root(두 번째 기준)의 조상이어도 같다
            claude_perm.outside_roots([claude_perm.REPO, w["repo"]])
        open(claude_perm.OUTSIDE_LIST, "w").write(json.dumps({"roots": [w["repo"]]}))  # 기준 폴더와 같은 루트는 빼고 계속한다
        self.assertEqual(claude_perm.outside_roots([w["repo"]]), [w["wt2"]])
        nested = os.path.join(w["repo"], ".claude", "worktrees", "x")  # 기본 checkout 안에 중첩된 worktree가 REPO면 기본 checkout이 조상 루트다
        subprocess.run(GIT + ["-C", w["repo"], "worktree", "add", "-q", nested], check=True, capture_output=True)
        open(claude_perm.OUTSIDE_LIST, "w").write(json.dumps({"roots": [w["other"]]}))
        with self.assertRaises(ValueError):
            claude_perm.outside_roots([nested])
        with mock.patch.object(sandbox, "REPO", nested):
            self.assertFalse(sandbox.available())  # 실행 차단(fail-closed)

    def test_f2_stage_inputs_refuses_inputs_inside_outside_roots_and_nested_worktrees(self):
        w = git_world(self)
        nested = os.path.join(w["repo"], ".claude", "worktrees", "x")
        subprocess.run(GIT + ["-C", w["repo"], "worktree", "add", "-q", nested], check=True, capture_output=True)
        copied = os.path.join(w["repo"], "listed")  # 목록 루트가 source_root 안에 있는 경우
        os.makedirs(copied)
        open(os.path.join(copied, "f.txt"), "w").write("x")
        open(claude_perm.OUTSIDE_LIST, "w").write(json.dumps({"roots": [copied]}))
        sha, task_dir, harness = sha_file(os.path.join(w["repo"], "f.txt")), os.path.join(w["base"], "t"), os.path.join(w["base"], "root")
        for rel in ("listed/f.txt", ".claude/worktrees/x/f.txt"):  # 목록의 루트, source_root 안에 중첩된 worktree(실행 시점 git worktree list)
            with self.assertRaises(ValueError, msg=rel):
                claude_perm.stage_inputs(task_dir, {"inputs": {rel: sha}}, w["repo"], harness)
        self.assertEqual(claude_perm.stage_inputs(task_dir, {"inputs": {"f.txt": sha}}, w["repo"], harness), ["f.txt"])  # 정상 입력은 복사
        self.assertFalse(os.path.exists(os.path.join(task_dir, "in", "listed")))

    def test_f3_star_entries_also_block_files_created_while_the_sandbox_runs(self):
        w = git_world(self)
        weird = os.path.join(w["base"], "a(b)+c")  # 정규식 특수문자가 든 경로도 글자 그대로 막는다
        os.makedirs(os.path.join(weird, "exp", "old"))
        open(os.path.join(weird, "exp", "old", "ref.json"), "w").write("OLD")
        sealed = claude_perm.sealed_paths([weird])
        prof = sandbox.profile(os.path.join(w["base"], "root"), None, sealed)
        self.assertIn("regex", prof)
        names = ["exp/new/ref.json", "EXP/NEW/REF.JSON", "exp/new/keep.json", "exp/old/ref.json", "exp/old/Ref.json"]
        proc = subprocess.Popen([sandbox.SANDBOX_EXEC, "-p", prof, sys.executable, "-B", "-c", LATE] + [os.path.join(weird, n) for n in names],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=sandbox.REPO)
        time.sleep(0.8)
        os.makedirs(os.path.join(weird, "exp", "new"))  # 프로필을 만든 뒤 sandbox 밖에서 생긴 파일
        for n in ("ref.json", "keep.json"):
            open(os.path.join(weird, "exp", "new", n), "w").write("NEW")
        out, err = proc.communicate()
        self.assertEqual(out.split("\n")[:5], ["1", "1", "NEW", "1", "1"], err[-300:])  # ref.json(대소문자 변형 포함)만 거절, 같은 폴더의 다른 파일은 읽힘

    def test_f4_available_and_sandboxed_also_seal_the_source_root(self):
        w = git_world(self)
        with mock.patch.dict(os.environ, {sandbox.SOURCE_ENV: w["repo"]}), mock.patch.object(sandbox, "profile", wraps=sandbox.profile) as spy:
            self.assertTrue(sandbox.available())
            self.assertEqual(sorted(sandbox.sandboxed(w["base"], SPEC)), ["peeker"])
            os.environ.pop(sandbox.SOURCE_ENV)  # main이 --source-root에서 스스로 정해야 한다
            self.assertEqual(runner.main([os.path.join(w["base"], "root"), SPEC, "--source-root", w["repo"], "--max", "0"]), 0)
            self.assertEqual(os.environ[sandbox.SOURCE_ENV], w["repo"])
        vault = os.path.join(w["repo"], "vault")
        self.assertEqual([vault in call.args[2] for call in spy.call_args_list], [True] * len(spy.call_args_list))  # 모든 호출이 source_root의 봉인 경로를 넣었다
        self.assertGreaterEqual(len(spy.call_args_list), 3)

    def test_history_folders_are_denied_and_sandbox_work_does_not_need_them(self):
        home = os.path.expanduser("~")
        folders = [os.path.join(home, ".claude", "projects"), os.path.join(home, ".claude-mem"), os.path.join(home, ".codex", "sessions")]
        with open(claude_perm.OUTSIDE_LIST, encoding="utf-8") as handle:
            self.assertTrue(set(folders) <= set(json.load(handle)["roots"]))
        prof = sandbox.profile(tempfile.mkdtemp(prefix="v2-root-"), None, claude_perm.sealed_paths([claude_perm.REPO]), claude_perm.outside_roots([claude_perm.REPO]))
        got = sandboxed(prof, [(f, "stat") for f in folders if os.path.exists(f)] + [(sys.executable, "read"), (os.path.join(claude_perm.REPO, "harness", "sandbox.py"), "read")])
        self.assertEqual(set(got[0][:-2]), {1}, got)  # 존재하는 대화 기록 폴더는 stat도 거절(내용·이름 목록은 열지 않았다)
        self.assertEqual(got[0][-2:], ["ok", "ok"])  # python·저장소 읽기는 그 폴더 없이 된다(전체 sandbox 시험 통과로도 확인)


if __name__ == "__main__":
    unittest.main()
