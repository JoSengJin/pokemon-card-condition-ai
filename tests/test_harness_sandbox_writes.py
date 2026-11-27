"""검증 결함 F1·F2: executor sandbox는 기본 쓰기 거절이다. 그 실행의 out/·실행별 전용 임시 폴더(TMPDIR)·/dev/null만 쓸 수 있고,
하네스 root(상위 폴더 rename 우회 포함)·저장소 소스·site-packages·홈·시스템 임시 폴더·다른 작업 out/ 쓰기와 launchd·LaunchServices·
AppleScript 실행 파일 실행은 실제 sandbox-exec 하위 프로세스(sandbox.run_one, runner와 같은 경로)에서 거절된다.
공격 executor는 혹시 쓰기에 성공하면 그 자리에서 지우고 이름을 되돌린 뒤 결과를 자기 out/에 남긴다(시험이 실제 상태를 더럽히지 않게)."""
import json
import os
import shutil
import subprocess
import sysconfig
import tempfile
import unittest

from harness import sandbox

SPEC = "tests.test_harness_sandbox_writes:EXECUTORS"


def attacker(task, out_dir):
    """하네스 root·저장소·site-packages·홈·/tmp 쓰기와 상위 폴더 rename, 실행 파일 실행을 시도한다. {이름: ok|denied:<errno>}."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(out_dir)))
    parent, tag = os.path.dirname(root), "harness_sbx_probe_%d" % os.getpid()
    targets = {"harness_state": os.path.join(root, "supervisor", "opstate.json"),
               "other_task_out": os.path.join(root, "tasks", "other", "out", "x"),
               "repo_source": os.path.join(sandbox.REPO, "harness", tag + ".py"),
               "site_packages": os.path.join(sysconfig.get_paths()["purelib"], tag + ".pth"),
               "home": os.path.join(os.path.expanduser("~"), "." + tag),
               "system_tmp": os.path.join("/private/tmp", tag),
               "own_out": os.path.join(out_dir, "probe.txt"), "own_tmp": os.path.join(os.environ["TMPDIR"], "probe.txt"),
               "dev_null": "/dev/null"}
    got = {}
    for name, path in targets.items():
        existed = os.path.exists(path)
        try:
            with open(path, "a") as handle:
                handle.write("")
            got[name] = "ok"
            if not existed and name not in ("own_out", "own_tmp"):
                os.unlink(path)  # 거절돼야 할 쓰기가 됐다: 흔적을 지운다(결과는 ok로 남는다)
        except OSError as exc:
            got[name] = "denied:%d" % exc.errno
    try:
        os.rename(parent, parent + "_moved")
        got["rename_parent"] = "ok"
        os.rename(parent + "_moved", parent)
    except OSError as exc:
        got["rename_parent"] = "denied:%d" % exc.errno
    for exe, args in (("/bin/launchctl", ["help"]), ("/usr/bin/osascript", ["-e", "1"]), ("/usr/bin/open", [])):
        try:
            subprocess.run([exe] + args, capture_output=True, timeout=30, check=False)
            got["exec " + exe] = "ok"
        except OSError as exc:
            got["exec " + exe] = "denied:%d" % exc.errno
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        json.dump(got, handle)
    return ["result.txt"]


def tmp_probe(task, out_dir):
    """TMPDIR에 쓰고 그 경로를 산출물에 남긴다."""
    with open(os.path.join(os.environ["TMPDIR"], "probe.txt"), "w") as handle:
        handle.write("tmp")
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        handle.write(os.environ["TMPDIR"])
    return ["result.txt"]


EXECUTORS = {"attacker": attacker, "tmp_probe": tmp_probe}


class SandboxWriteTest(unittest.TestCase):
    def _root(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root = os.path.join(base, "parent", "root")
        for sub in ("supervisor", os.path.join("tasks", "k", "out"), os.path.join("tasks", "other", "out")):
            os.makedirs(os.path.join(root, sub))
        with open(os.path.join(root, "supervisor", "opstate.json"), "w", encoding="utf-8") as handle:
            handle.write("ORIG")
        return root

    def test_default_deny_blocks_root_rename_repo_site_home_and_launch_tools(self):
        root = self._root()
        out = os.path.join(root, "tasks", "k", "out")
        self.assertEqual(sandbox.run_one(root, SPEC, "attacker", {}, out), ["result.txt"])
        with open(os.path.join(out, "result.txt"), encoding="utf-8") as handle:
            got = json.load(handle)
        allowed = {"own_out", "own_tmp", "dev_null"}
        self.assertEqual({k for k, v in got.items() if v == "ok"}, allowed, got)
        self.assertTrue(all(v == "denied:1" for k, v in got.items() if k not in allowed), got)
        with open(os.path.join(root, "supervisor", "opstate.json"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "ORIG")
        self.assertEqual(os.listdir(os.path.join(root, "tasks", "other", "out")), [])
        self.assertFalse(os.path.exists(os.path.dirname(root) + "_moved"))

    def test_each_run_gets_a_private_tmpdir_that_is_removed_afterwards(self):
        root = self._root()
        out = os.path.join(root, "tasks", "k", "out")
        sandbox.run_one(root, SPEC, "tmp_probe", {}, out)
        with open(os.path.join(out, "result.txt"), encoding="utf-8") as handle:
            used = handle.read()
        self.assertNotEqual(os.path.realpath(used), os.path.realpath(tempfile.gettempdir()))
        self.assertFalse(os.path.exists(used))  # 실행이 끝나면 지운다
        self.assertNotEqual(os.path.commonpath([os.path.realpath(root), os.path.realpath(used)]), os.path.realpath(root))


if __name__ == "__main__":
    unittest.main()
