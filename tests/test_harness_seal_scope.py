"""사용자 D4 봉인 범위: glob 항목 풀이, 저장소 밖 작업 폴더 루트(sealed_outside_roots.json + git worktree list) 읽기 거절, 자기 루트 제외, 규칙 수 증가 실측.

임시 git 저장소·가짜 목록만 쓴다(실제 봉인 자료 내용은 열지 않는다). 실제 추적 목록은 이름·형식·실행 시간만 확인한다.
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

from harness import claude_perm, ledger, sandbox
from harness import contract as ct
from tests.test_harness_support import make_contract

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
PEEK = r'''
import json, os, sys
def probe(path, how):
    try:
        (os.listdir if how == "ls" else os.stat if how == "stat" else lambda p: open(p, "rb").read(4))(path)
        return "ok"
    except OSError as exc:
        return exc.errno
print(json.dumps([probe(p, how) for p, how in json.loads(sys.argv[1])]))
'''


def sandboxed(prof, probes):
    """실제 sandbox-exec 안에서 [(경로, read|stat|ls)]를 시도해 결과(ok 또는 errno) 목록을 돌려준다."""
    done = subprocess.run([sandbox.SANDBOX_EXEC, "-p", prof, sys.executable, "-B", "-c", PEEK, json.dumps(probes)], cwd=sandbox.REPO,
                          capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return json.loads(done.stdout.strip().split("\n")[-1]), done.stderr[-300:]


def git_world(case):
    """임시 저장소 repo(f.txt 커밋)와 그 worktree wt2, 따로 있는 other, exp/e1·e2/ref.json 용 폴더. 목록 파일을 만들어 claude_perm에 연결한다.
    OUTSIDE 루트 = [other, repo(자기 자신), gone(없는 경로)], SEALED = ["vault", "exp/*/ref.json"]. base 경로 dict를 돌려준다."""
    base = os.path.realpath(tempfile.mkdtemp(prefix="seal-scope-"))
    case.addCleanup(shutil.rmtree, base, True)
    repo, wt2, other = (os.path.join(base, n) for n in ("repo", "wt2", "other"))
    for folder, rel in ((repo, "f.txt"), (other, "f.txt"), (repo, "vault/s.txt"), (repo, "exp/e1/ref.json"), (repo, "exp/e1/keep.json")):
        os.makedirs(os.path.dirname(os.path.join(folder, rel)), exist_ok=True)
        with open(os.path.join(folder, rel), "w") as handle:
            handle.write("x")
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "m"], ["worktree", "add", "-q", wt2]):
        subprocess.run(GIT + ["-C", repo] + args, check=True, capture_output=True)
    for name, text in (("outside.json", {"roots": [other, repo, base + "/gone"]}), ("sealed.json", {"paths": ["vault", "exp/*/ref.json"]})):
        with open(os.path.join(base, name), "w") as handle:
            json.dump(text, handle)
    for attr, name in (("OUTSIDE_LIST", "outside.json"), ("SEALED_LIST", "sealed.json")):
        patcher = mock.patch.object(claude_perm, attr, os.path.join(base, name))
        patcher.start()
        case.addCleanup(patcher.stop)
    return {"base": base, "repo": repo, "wt2": wt2, "other": other}


class SealScopeTest(unittest.TestCase):
    def test_star_entries_are_resolved_at_run_time_and_cover_new_files(self):
        w = git_world(self)
        e1, e2 = (os.path.join(w["repo"], "exp", n, "ref.json") for n in ("e1", "e2"))
        self.assertIn(e1, claude_perm.sealed_paths([w["repo"]]))
        self.assertNotIn(os.path.join(w["repo"], "exp", "e1", "keep.json"), claude_perm.sealed_paths([w["repo"]]))
        os.makedirs(os.path.dirname(e2))
        open(e2, "w").write("y")  # 목록을 고치지 않고 나중에 생긴 파일도 다음 실행부터 막힌다
        self.assertIn(e2, claude_perm.sealed_paths([w["repo"]]))
        prof = sandbox.profile(os.path.join(w["base"], "root"), None, claude_perm.sealed_paths([w["repo"]]))
        self.assertEqual(sandboxed(prof, [(e1, "read"), (e2, "read"), (os.path.join(w["repo"], "exp/e1/keep.json"), "read")])[0], [1, 1, "ok"])
        for bad in ('{"paths": ["a/?"]}', '{"paths": ["a/[b]"]}'):
            open(claude_perm.SEALED_LIST, "w").write(bad)
            with self.assertRaises(ValueError, msg=bad):
                claude_perm.sealed_paths([w["repo"]])

    def test_outside_roots_come_from_the_list_and_git_worktrees_without_own_roots_or_ancestors(self):
        w = git_world(self)
        got = claude_perm.outside_roots([w["repo"], None])
        self.assertEqual(got, sorted([w["other"], w["wt2"], w["base"] + "/gone"]))  # repo(자기) 제외, 목록에 없는 wt2는 git worktree list로 추가
        self.assertEqual(claude_perm.outside_roots([w["wt2"]]), sorted([w["other"], w["base"] + "/gone", w["repo"]]))  # 기준이 바뀌면 자기 루트가 바뀐다
        bads = ["missing", "link", "not json", "[]", '{"roots": []}', '{"roots": ["rel"]}', '{"roots": ["/"]}', '{"roots": ["/a/../b"]}',
                '{"roots": ["/a/"]}', '{"roots": ["/a\\"b"]}', '{"roots": [1]}', '{"roots": "/a"}']
        for bad in bads:
            if os.path.lexists(claude_perm.OUTSIDE_LIST):
                os.remove(claude_perm.OUTSIDE_LIST)
            if bad == "link":
                open(claude_perm.OUTSIDE_LIST + ".real", "w").write('{"roots": ["/x"]}')
                os.symlink(claude_perm.OUTSIDE_LIST + ".real", claude_perm.OUTSIDE_LIST)
            elif bad != "missing":
                open(claude_perm.OUTSIDE_LIST, "w").write(bad)
            with self.assertRaises(ValueError, msg=bad):
                claude_perm.outside_roots([w["repo"]])
        open(claude_perm.OUTSIDE_LIST, "w").write('{"roots": ["/x"]}')  # 목록은 정상, git만 실패하는 경우
        with self.assertRaises(ValueError):  # git 저장소가 아니면 worktree 목록을 모른다 → 보장 못 함 → 거절
            claude_perm.outside_roots([tempfile.gettempdir()])

    def test_sandbox_denies_other_roots_and_worktrees_but_not_its_own_root_or_its_python(self):
        w = git_world(self)
        fake = os.path.join(w["other"], "venv")  # outside 루트 안에 있는 python 환경 흉내: prefix가 그 안이면 그 폴더만 다시 읽힌다
        os.makedirs(fake)
        open(os.path.join(fake, "ok.txt"), "w").write("x")
        with mock.patch.object(sys, "prefix", fake), mock.patch.object(sys, "exec_prefix", fake):
            prof = sandbox.profile(os.path.join(w["base"], "root"), os.path.join(w["base"], "run"), claude_perm.sealed_paths([w["repo"]]),
                                   claude_perm.outside_roots([w["repo"]]))
        probes = [(os.path.join(w["other"], "f.txt"), "read"), (w["other"], "stat"), (w["other"], "ls"), (os.path.join(w["wt2"], "f.txt"), "read"),
                  (os.path.join(w["repo"], "f.txt"), "read"), (os.path.join(w["repo"], "vault", "s.txt"), "read"), (os.path.join(fake, "ok.txt"), "read")]
        self.assertEqual(sandboxed(prof, probes)[0], [1, 1, 1, 1, "ok", 1, "ok"])  # 다른 루트·worktree 거절, 자기 저장소 정상, 봉인 목록 거절, python 환경만 예외
        task = make_contract("O", task_type="peeker", inputs={"src": w["repo"]})
        final = os.path.join(w["base"], "root", "tasks", ct.task_key(task), "out")
        with mock.patch.dict(os.environ, {sandbox.SOURCE_ENV: w["repo"]}), mock.patch.object(sandbox, "profile", wraps=sandbox.profile) as spy:
            sandbox.run_one(os.path.join(w["base"], "root"), "tests.test_harness_sandbox_read:EXECUTORS", "peeker", task, final)
        self.assertIn(w["other"], spy.call_args.args[3])  # run_one이 실제로 저장소 밖 루트를 프로필에 넘긴다
        with self.assertRaises(ValueError):  # 하네스 root나 실행 폴더가 거절 루트 안이면 읽을 수 없게 되므로 프로필을 만들지 않는다
            sandbox.profile(os.path.join(w["other"], "root"), None, claude_perm.sealed_paths([w["repo"]]), claude_perm.outside_roots([w["repo"]]))
        with self.assertRaises(ValueError):
            sandbox.profile(os.path.join(w["base"], "root"), os.path.join(w["other"], "run"), claude_perm.sealed_paths([w["repo"]]), [w["other"]])

    def test_real_lists_keep_sandbox_exec_working_and_fast(self):
        """실제 추적 목록(봉인 경로 + 저장소 밖 루트 + 현재 worktree 목록)으로 만든 프로필: 규칙 수·실행 시간 실측, 자기 저장소·python 읽기 성공."""
        with open(claude_perm.SEALED_LIST, encoding="utf-8") as handle:
            listed = json.load(handle)["paths"]
        with open(claude_perm.OUTSIDE_LIST, encoding="utf-8") as handle:
            roots = json.load(handle)["roots"]
        self.assertEqual((len(listed), len(roots)), (144, 156))
        for needed in ("artifacts/cohort2-seal-20261123", "artifacts/cohort-seal-20261123", "artifacts/d1-testset-20261103", "artifacts/d1b-surface-20261104",
                       "artifacts/c4-expansion-20261103/answers-holdout-5.txt", "artifacts/ebay-independent-20261119-a", "artifacts/experiments/*/reference.json"):
            self.assertIn(needed, listed)
        self.assertFalse([p for p in listed if p.split("/")[0] in ("card_condition", "harness", "tests", "tools", "docs")])
        base, src = claude_perm.REPO, tempfile.mkdtemp(prefix="seal-scope-src-")
        self.addCleanup(shutil.rmtree, src, True)
        subprocess.run(GIT + ["-C", src, "init", "-q"], check=True, capture_output=True)
        sealed, outside = claude_perm.sealed_paths([base, os.path.realpath(src)]), claude_perm.outside_roots([base, os.path.realpath(src)])
        self.assertFalse([r for r in outside if os.path.commonpath([r, base]) == r])  # 자기 저장소·조상은 거절 대상이 아니다
        prof = sandbox.profile(tempfile.mkdtemp(prefix="seal-scope-root-"), None, sealed, outside)
        started = time.time()
        got, err = sandboxed(prof, [(os.path.join(base, "harness", "sandbox.py"), "read"), (sys.executable, "read")])
        took = time.time() - started
        self.assertEqual(got, ["ok", "ok"], err)
        self.assertLess(took, 10, "규칙 %d줄에서 sandbox-exec python 실행 %.2f초" % (prof.count("\n"), took))
        self.assertTrue(sandbox.available())
        main = subprocess.run(["git", "-C", base, "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout.split("\n")[0][len("worktree "):]
        if os.path.realpath(main) != os.path.realpath(base):  # 이 worktree가 기본 checkout이 아니면 기본 checkout 전체가 거절되고 python 환경만 예외다
            self.assertEqual(sandboxed(prof, [(os.path.join(main, "AGENTS.md"), "read")])[0], [1])

    def test_missing_outside_list_stops_every_sandbox_entry_point(self):
        w = git_world(self)
        os.remove(claude_perm.OUTSIDE_LIST)
        self.assertFalse(sandbox.available())
        task = make_contract("F", task_type="peeker", inputs={})
        final = os.path.join(w["base"], "root", "tasks", ct.task_key(task), "out")
        with mock.patch.dict(os.environ, {sandbox.SOURCE_ENV: w["repo"]}), mock.patch.object(sandbox, "REPO", w["repo"]):
            with self.assertRaises(ValueError):
                sandbox.run_one(os.path.join(w["base"], "root"), "tests.test_harness_sandbox_read:EXECUTORS", "peeker", task, final)
            with self.assertRaises(ValueError):
                sandbox.sandboxed(os.path.join(w["base"], "root"), "tests.test_harness_sandbox_read:EXECUTORS")
        self.assertFalse(os.path.exists(final))  # 아무것도 만들거나 실행하지 않았다


if __name__ == "__main__":
    unittest.main()
