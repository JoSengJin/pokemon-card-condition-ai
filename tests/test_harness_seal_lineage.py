"""계보 봉인 폴더 보강(2026-11-28): 정답 rows가 든 result.json은 이름 glob(reference.json·observations.json) 밖이라 열려 있었다. 계보가 봉인에 닿는
실험 폴더 22개를 폴더 전체로 목록에 넣었다. 실제 목록은 이름만 확인하고, sandbox 거절은 합성 폴더로 실측한다(실제 봉인 파일은 쓰지 않는다).
"""
import errno
import json
import os
import unittest

from harness import claude_perm, sandbox
from tests.test_harness_seal_scope import git_world, sandboxed

LINEAGE = [
    "20261024T103712-41c8db99",
    "20261024T103800-512a2260",
    "20261025T122011-647b0e9c",
    "20261031T075821-c058c6e6",
    "20261031T080149-1f624f3e",
    "20261031T093842-2ba28932",
    "20261031T220908-5c8faa3f",
    "20261031T224358-d406cd3d",
    "20261101T024340-1989a418",
    "20261101T035717-b34352c6",
    "20261102T041234-c2a01da3",
    "20261102T103444-ec2316a1",
    "20261102T103455-3df515c8",
    "20261102T123424-b5ff706a",
    "20261102T135642-1549ba76",
    "20261102T145448-7876bfd4",
    "20261102T215710-f9160113",
    "20261102T215718-870c2647",
    "20261102T233115-f405c24a",
    "20261115T222335-d9dacbe8",
    "20261115T214158-7d77f37b",
    "20261021T204152-d9cd6f88"
]
# 봉인 계보 폴더의 result.json을 참조 사슬로 이어받는 개발 계보(전이 폐포, plan.json 메타데이터만으로 계산). 미확인은 확인 전 차단(D4).
CLOSURE = [
    "20261027T132418-8a5aa6ae",
    "20261027T133213-807fae2a",
    "20261027T144107-8f7674cd",
    "20261027T145641-21c22382",
    "20261027T211902-7ae1cc41",
    "20261027T212933-6784927d",
    "20261027T222515-1d33d82d",
    "20261027T225304-e0ad355a",
    "20261028T070550-da6d6dad",
    "20261028T070837-27da5a1b",
    "20261028T101236-890223b7",
    "20261028T101319-9e1f577e",
    "20261028T101414-6b20743e",
    "20261028T101838-cb8057c6",
    "20261028T102607-3d234a18",
    "20261028T103903-512b1606",
    "20261028T130920-50860931",
    "20261028T131334-3c85d76b",
    "20261028T203138-7d30f998",
    "20261029T203620-18f694cb"
]
FILES = ["result.json", "evaluation.json", "index.html", "images/a.jpg"]  # 이름 glob 밖이던 파일들


class SealLineageTest(unittest.TestCase):
    def test_real_list_has_every_lineage_folder_and_keeps_the_old_globs(self):
        with open(claude_perm.SEALED_LIST, encoding="utf-8") as handle:
            paths = json.load(handle)["paths"]
        for name in LINEAGE + CLOSURE:
            self.assertIn("artifacts/experiments/" + name, paths, name)  # 새 항목을 빼면 여기서 실패한다(결함 주입)
        self.assertTrue({"artifacts/experiments/*/reference.json", "artifacts/experiments/*/observations.json"} <= set(paths))
        self.assertEqual(len(paths), len(set(paths)))

    def test_lineage_folder_entry_denies_result_json_inside_the_sandbox(self):
        w = git_world(self)
        for rel in FILES + ["../other-exp/result.json"]:
            path = os.path.normpath(os.path.join(w["repo"], "exp", "lin1", rel))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as handle:
                handle.write("x")
        probes = [(os.path.join(w["repo"], "exp", rel), "read") for rel in ["lin1/" + f for f in FILES] + ["other-exp/result.json"]]
        for entries, want in ((["vault", "exp/*/ref.json", "exp/lin1"], [errno.EPERM] * len(FILES) + ["ok"]),  # 항목이 있으면 PermissionError, 목록 밖 폴더는 읽힌다
                              (["vault", "exp/*/ref.json"], ["ok"] * (len(FILES) + 1))):  # 항목이 없으면 열린다(이 시험이 항목 유무를 가른다는 대조)
            with open(os.path.join(w["base"], "sealed.json"), "w") as handle:
                json.dump({"paths": entries}, handle)
            prof = sandbox.profile(os.path.join(w["base"], "root"), None, claude_perm.sealed_paths([w["repo"]]))
            self.assertEqual(sandboxed(prof, probes)[0], want, entries)


if __name__ == "__main__":
    unittest.main()
