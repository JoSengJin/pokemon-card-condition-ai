"""봉인 자료 읽기 차단(합성 폴더, 실제 sandbox-exec 하위 프로세스): claude_perm.SEALED_LIST의 경로를 sandbox 프로필이 읽기 거절
(deny file-read* subpath)하고 claude_perm.stage_inputs가 입력 복사를 거절한다. 목록 파일이 없거나 링크·형식 오류면 둘 다 fail-closed.

- 목록과 가짜 저장소(source)는 시험마다 임시로 만든다. 가짜 저장소는 HARNESS_SOURCE_ROOT로 프로필에 들어간다(runner가 넣는 값과 같다).
  봉인 폴더 이름에 gold·seal을 쓰지 않는다(이름 규칙이 아니라 목록이 막는지 본다).
- 대조: 같은 프로필에서 deny file-read* 줄만 빼면 같은 읽기가 성공한다(규칙이 막는 것이지 파일이 없어서가 아님).
- 한계(막지 못함, 시험하지 않음): sandbox 밖에서 미리 만든 하드 링크는 봉인 경로 밖 이름으로 읽힌다(task 문서).
"""
import json
import os
import shutil
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

from harness import claude_perm, sandbox
from harness import contract as ct
from harness.cas import sha_file
from harness.experiment_exec import SOURCE_ENV
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_sandbox_read:EXECUTORS"
PROBES = ("read", "stat", "listdir", "file_entry", "entry_link_target", "via_symlink", "hardlink", "case_variant", "open_ok", "stdlib")


def peeker(task, out_dir):
    """sandbox 안 executor: 봉인 경로 읽기·정상 읽기를 시도해 결과를 result.txt에 쓴다."""
    src, got = task["inputs"]["src"], {}
    tries = (lambda: open(os.path.join(src, "vault", "a.json")).read(), lambda: os.stat(os.path.join(src, "vault", "a.json")),
             lambda: os.listdir(os.path.join(src, "vault")), lambda: open(os.path.join(src, "loose.json")).read(),
             lambda: open(os.path.join(src, "hidden", "b.json")).read(), lambda: open(os.path.join(src, "open", "link.json")).read(),
             lambda: os.link(os.path.join(src, "vault", "a.json"), os.path.join(os.environ["TMPDIR"], "h")),
             lambda: open(os.path.join(src, "VAULT", "A.json")).read(),
             lambda: open(os.path.join(src, "open", "ok.json")).read(),
             lambda: __import__("sqlite3") and __import__("ssl") and open(sys.executable, "rb").read(4))
    for name, attempt in zip(PROBES, tries):
        try:
            attempt()
            got[name] = "ok"
        except OSError as exc:
            got[name] = "denied:%d" % exc.errno
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        json.dump(got, handle)
    return ["result.txt"]


EXECUTORS = {"peeker": peeker}


def fake_repo(test, listing_text='{"paths": ["vault", "loose.json", "alias", "caf\u00e9"]}'):
    """가짜 저장소 src: vault/(폴더 항목), loose.json(파일 항목), alias → hidden(링크 항목), café/(NFC 이름 항목), open/ok.json(정상),
    open/link.json → vault/a.json.
    claude_perm.SEALED_LIST를 임시 목록으로, HARNESS_SOURCE_ROOT를 src로 바꾼다. (base, src, listing)."""
    base = os.path.realpath(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, base, True)
    src, listing = os.path.join(base, "src"), os.path.join(base, "list.json")
    for rel in ("vault/a.json", "loose.json", "hidden/b.json", "open/ok.json", "caf\u00e9/c.json"):
        os.makedirs(os.path.dirname(os.path.join(src, rel)), exist_ok=True)
        with open(os.path.join(src, rel), "w") as handle:
            handle.write('{"fake": "%s"}' % rel)
    os.symlink(os.path.join(src, "hidden"), os.path.join(src, "alias"))
    os.symlink(os.path.join(src, "vault", "a.json"), os.path.join(src, "open", "link.json"))
    with open(listing, "w") as handle:
        handle.write(listing_text)
    for patcher in (mock.patch.object(claude_perm, "SEALED_LIST", listing), mock.patch.dict(os.environ, {SOURCE_ENV: src})):
        patcher.start()
        test.addCleanup(patcher.stop)
    return base, src, listing


class SealedReadTest(unittest.TestCase):
    def _run(self, base, src):
        task = make_contract("R", task_type="peeker", inputs={"src": src})
        final = os.path.join(base, "root", "tasks", ct.task_key(task), "out")
        self.assertEqual(sandbox.run_one(os.path.join(base, "root"), SPEC, "peeker", task, final), ["result.txt"])
        with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
            return json.load(handle)

    def test_sealed_reads_are_refused_in_sandbox_but_normal_reads_and_stdlib_work(self):
        base, src, _ = fake_repo(self)
        text = sandbox.profile(os.path.join(base, "root"), tempfile.mkdtemp(dir=base))
        for rel in ("vault", "loose.json", "hidden"):  # 링크 항목(alias)은 실제 경로(hidden)로 적힌다
            self.assertIn('(subpath "%s")' % os.path.join(src, rel), text)
        self.assertEqual(self._run(base, src), dict({p: "denied:1" for p in PROBES[:8]}, open_ok="ok", stdlib="ok"))
        original = sandbox.profile  # 대조(결함 주입): deny file-read* 줄만 빼면 같은 읽기가 성공한다
        bare = lambda *args: "\n".join(line for line in original(*args).split("\n") if not line.startswith("(deny file-read*"))
        with mock.patch.object(sandbox, "profile", bare):
            got = self._run(base, src)
        self.assertEqual({p: got[p] for p in PROBES[:6]}, {p: "ok" for p in PROBES[:6]})

    def test_stage_inputs_refuses_listed_paths_by_real_path_and_keeps_name_rule(self):
        base, src, _ = fake_repo(self)
        sha = lambda rel: sha_file(os.path.join(src, rel))
        task_dir, harness_root = os.path.join(base, "task"), os.path.join(base, "root")
        nfd = unicodedata.normalize("NFD", "caf\u00e9") + "/c.json"  # 목록은 NFC, 입력은 NFD(APFS는 같은 파일로 연다)
        for rel in ("vault/a.json", "loose.json", "hidden/b.json", "VAULT/a.json", "Vault/A.JSON", "LOOSE.json", nfd):
            with self.assertRaises(ValueError, msg=rel):  # hidden/b.json: 이름에 봉인 표시가 없고 링크 항목의 실제 경로 아래
                claude_perm.stage_inputs(task_dir, {"inputs": {rel: sha(rel)}}, src, harness_root)
        os.makedirs(os.path.join(harness_root, "tasks", "k"))
        shutil.copy(os.path.join(src, "open", "ok.json"), os.path.join(harness_root, "tasks", "k", "x.json"))
        with self.assertRaises(ValueError):  # 하네스 root를 대소문자만 바꾼 이름으로 가리켜도 root 안이다(기존 비교의 같은 약점)
            claude_perm.stage_inputs(task_dir, {"inputs": {"x.json": sha("open/ok.json")}}, os.path.join(base, "ROOT", "tasks", "k"),
                                     harness_root)
        self.assertEqual(claude_perm.stage_inputs(task_dir, {"inputs": {"open/ok.json": sha("open/ok.json")}}, src, harness_root),
                         ["open/ok.json"])
        os.makedirs(os.path.join(src, "gold"))
        shutil.copy(os.path.join(src, "open", "ok.json"), os.path.join(src, "gold", "c.json"))
        with self.assertRaises(ValueError):  # 기존 이름 규칙도 그대로(이중 차단)
            claude_perm.stage_inputs(task_dir, {"inputs": {"gold/c.json": sha("gold/c.json")}}, src, harness_root)

    def test_missing_linked_or_malformed_list_fails_closed(self):
        for bad in ("missing", "link", "not json", "[]", '{"paths": []}', '{"paths": ["/abs"]}', '{"paths": ["a/../b"]}',
                    '{"paths": ["a\\"b"]}', '{"paths": [1]}', '{"paths": "vault"}', '{"paths": ["a//b"]}'):
            base, src, listing = fake_repo(self, bad)
            if bad == "missing":
                os.remove(listing)
            elif bad == "link":
                good = os.path.join(base, "good.json")
                with open(good, "w") as handle:
                    handle.write('{"paths": ["vault"]}')
                os.remove(listing)
                os.symlink(good, listing)
            with self.assertRaises(ValueError, msg=bad):
                sandbox.profile(os.path.join(base, "root"))
            self.assertFalse(sandbox.available(), bad)
            sha = sha_file(os.path.join(src, "open", "ok.json"))
            with self.assertRaises(ValueError, msg=bad):
                claude_perm.stage_inputs(os.path.join(base, "task"), {"inputs": {"open/ok.json": sha}}, src, os.path.join(base, "root"))

    def test_tracked_list_loads_and_holds_only_data_paths(self):
        with open(claude_perm.SEALED_LIST, encoding="utf-8") as handle:
            listed = json.load(handle)["paths"]
        self.assertIn("artifacts/d1-testset-20261103", listed)
        self.assertFalse([p for p in listed if p.split("/")[0] in ("card_condition", "harness", "tests", "tools", "docs")])
        real = claude_perm.sealed_paths([claude_perm.REPO])
        self.assertIn(os.path.realpath(os.path.join(claude_perm.REPO, "artifacts/d1-testset-20261103")), real)
        self.assertTrue(sandbox.available())  # 실제 목록으로 만든 프로필이 이 macOS에서 적용된다


if __name__ == "__main__":
    unittest.main()
