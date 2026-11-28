"""2차 결함 G1: 하네스의 파일 쓰기는 예측 가능한 임시 이름(<대상>.tmp.<pid>)을 쓰지 않고 mkstemp(O_EXCL) 새 파일 + os.replace로 한다.
그 자리에 링크를 깔아 두어도 링크 대상(하네스 소스·상태·root 밖 파일)을 덮어쓰지 않는다. 대상이나 그 폴더가 링크면 쓰지 않는다.
대상: cas.put·restore·get, jsonio.write_json, claude_perm.stage_inputs(입력 복사), queue.claim의 CORRUPT 복구.
신뢰하지 않는 폴더에서 읽을 때(safefs.open_regular)는 중간·마지막 어느 조각도 링크를 따라가지 않고, 일반 파일·링크 수 1만 연다."""
import hashlib
import os
import pathlib
import shutil
import tempfile
import unittest

from harness import cas, claude_perm, jsonio
from tests.test_harness_support import BOOT, claim, finish, make_contract


def _plant(case, *dests):
    """dests마다 옛 임시 이름(<dest>.tmp.<현재 pid>)에 피해 파일로 가는 심볼릭 링크를 깐다. 피해 파일 경로."""
    base = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, base, True)
    victim = os.path.join(base, "victim.txt")
    pathlib.Path(victim).write_text("ORIG")
    for dest in dests:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.symlink(victim, "%s.tmp.%d" % (dest, os.getpid()))
    return victim


class SafeWriteTest(unittest.TestCase):
    def test_writes_do_not_follow_links_planted_at_the_old_tmp_names(self):
        root = tempfile.mkdtemp()
        store, src = os.path.join(root, "cas"), os.path.join(root, "src")
        os.makedirs(src)
        pathlib.Path(src, "a.txt").write_bytes(b"payload")
        sha = hashlib.sha256(b"payload").hexdigest()
        restored, got, state = (os.path.join(root, "out", n) for n in ("r.txt", "g.txt", "state.json"))
        victim = _plant(self, cas.blob_path(store, sha), restored, got, state, os.path.join(root, "task", "in", "a.txt"))
        self.assertEqual(cas.put(store, os.path.join(src, "a.txt")), sha)
        self.assertEqual(cas.restore(store, [(sha, restored)]), [])
        cas.get(store, sha, got)
        jsonio.write_json(state, {"ok": True})
        claude_perm.stage_inputs(os.path.join(root, "task"), {"inputs": {"a.txt": sha}}, src, os.path.join(root, "harness"))
        self.assertEqual(pathlib.Path(victim).read_text(), "ORIG")  # 링크 대상은 그대로
        for path in (cas.blob_path(store, sha), restored, got, os.path.join(root, "task", "in", "a.txt")):
            self.assertEqual(pathlib.Path(path).read_bytes(), b"payload", path)
            self.assertFalse(os.path.islink(path), path)
        self.assertEqual(jsonio.read_json(state), {"ok": True})

    def test_link_targets_and_link_folders_are_not_written(self):
        root = tempfile.mkdtemp()
        store = os.path.join(root, "cas")
        os.makedirs(os.path.join(root, "src"))
        pathlib.Path(root, "src", "a.txt").write_bytes(b"payload")
        sha = cas.put(store, os.path.join(root, "src", "a.txt"))
        victim = _plant(self)
        elsewhere = os.path.dirname(victim)
        os.makedirs(os.path.join(root, "out"))
        os.symlink(victim, os.path.join(root, "out", "link.txt"))  # 대상 자체가 링크
        os.symlink(elsewhere, os.path.join(root, "out", "sub"))  # 대상 폴더가 링크
        for dest in (os.path.join(root, "out", "link.txt"), os.path.join(root, "out", "sub", "x.txt")):
            self.assertEqual(cas.restore(store, [(sha, dest)]), [dest])
            with self.assertRaises(cas.CasError):
                cas.get(store, sha, dest)
            with self.assertRaises(OSError):
                jsonio.write_json(dest, {"x": 1})
        self.assertEqual(pathlib.Path(victim).read_text(), "ORIG")
        self.assertEqual(sorted(os.listdir(elsewhere)), ["victim.txt"])

    def test_open_regular_follows_no_link_and_accepts_only_single_link_regular_files(self):
        from harness import safefs  # 2차 수정에서 새로 둔 모듈(수정 전에는 없다)
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        top = os.path.join(base, "stage")
        os.makedirs(os.path.join(top, "d"))
        pathlib.Path(top, "ok.txt").write_text("ok")
        pathlib.Path(top, "d", "ok.txt").write_text("nested")
        pathlib.Path(base, "outside.txt").write_text("outside")
        os.symlink(os.path.join(base, "outside.txt"), os.path.join(top, "link.txt"))
        os.symlink(os.path.join(top, "d"), os.path.join(top, "dlink"))
        os.link(os.path.join(top, "ok.txt"), os.path.join(top, "hard.txt"))
        os.mkfifo(os.path.join(top, "fifo"))
        fd = os.open(top, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        got = safefs.open_regular(fd, "d/ok.txt")
        self.assertEqual(os.read(got, 100), b"nested")
        os.close(got)
        for rel in ("link.txt", "dlink/ok.txt", "hard.txt", "ok.txt", "fifo", "d", "missing", "../outside.txt", "d/../ok.txt"):
            with self.assertRaises(OSError, msg=rel):  # ok.txt도 hard.txt와 링크 수 2라 거절
                os.close(safefs.open_regular(fd, rel))

    def test_corrupt_restore_through_claim_does_not_follow_planted_links(self):
        root = tempfile.mkdtemp()
        key, _ = finish(root, make_contract("a"), 1.0, payload=b"original")
        out = os.path.join(root, "tasks", key, "out")
        pathlib.Path(out, "result.txt").write_bytes(b"tampered")  # 하네스 밖 무언가가 확정 산출물을 바꿨다
        victim = _plant(self, os.path.join(out, "result.txt"))
        res = claim(root, key, os.getpid(), BOOT, 5.0)
        self.assertEqual((res["ok"], res["reason"]), (False, "skip"))  # CAS에서 되살리고 다시 검증 통과
        self.assertEqual(pathlib.Path(out, "result.txt").read_bytes(), b"original")
        self.assertEqual(pathlib.Path(victim).read_text(), "ORIG")


if __name__ == "__main__":
    unittest.main()
