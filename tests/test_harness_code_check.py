"""sandbox 밖 runner의 code_sha 검증 결과를 어댑터에 전달하는 경로(experiment_exec.record_code·check_code) 판정 시험.

6c564d4 뒤 sandbox 안에서는 git을 못 읽는다(봉인 파일이 git 객체에 있다). runner가 verify_code 직후 작업 폴더 code-check.json에 code_sha 커밋의
파일별 git blob SHA를 쓰고, 어댑터는 git 없이 그 파일만 읽어 현재 파일 내용을 재계산해 대조한다. 가짜 저장소·가짜 봉인 목록만 쓴다.
runner 연결·실제 sandbox는 test_harness_code_check_run.
"""
import json
import os
import shutil
import subprocess
import unittest

from harness.experiment_exec import CHECK_ENV, CHECK_NAME
from tests.harness_code_check_kit import edit, make_world, refused

ZERO = "0" * 40


class CodeCheckTest(unittest.TestCase):
    def test_recorded_result_passes_and_states_its_scope(self):
        make_world(self)
        data = json.load(open(self.path, encoding="utf-8"))
        self.assertEqual((self.path, data["code_sha"], data["source_root"]), (os.path.join(self.tdir, CHECK_NAME), self.head, self.src))
        self.assertEqual(sorted(data["files"]), ["a.py", "experiment", "ln", "sub/b.txt"])
        self.assertEqual((data["files"]["experiment"][0], data["files"]["ln"][0]), ("100755", "120000"))
        self.assertEqual(data["sealed_skipped"], ["vault/s.json"])  # 봉인 목록 아래 추적 파일: sandbox가 읽을 수 없어 뺀 사실을 남긴다
        self.assertFalse(refused(self.task, self.src))
        with open(os.path.join(self.src, "vault", "s.json"), "w", encoding="utf-8") as handle:
            handle.write("{} \n")  # 대조에서 뺀 파일은 바뀌어도 이 대조가 막지 않는다(한계: 실행 코드가 아니라는 전제, task 문서)
        self.assertFalse(refused(self.task, self.src))

    def test_missing_malformed_linked_mismatched_or_changed_results_are_refused(self):
        cases = ("env_unset", "missing", "not_json", "extra_key", "symlink", "hardlink", "other_name", "linked_dir", "code_sha", "other_source",
                 "changed_same_size", "deleted", "to_symlink", "mode", "link_target", "no_experiment", "escape", "bad_mode", "bad_blob")
        got = {}
        for name in cases:
            make_world(self)
            a, root = os.path.join(self.src, "a.py"), os.path.join(self.src, "ln")
            workdir, task = self.src, self.task
            if name == "env_unset":
                del os.environ[CHECK_ENV]
            elif name == "missing":
                os.remove(self.path)
            elif name == "not_json":
                open(self.path, "w").write("nope")
            elif name == "extra_key":
                edit(self.path, top={"extra": 1})
            elif name == "symlink":
                os.rename(self.path, self.path + ".real")
                os.symlink(self.path + ".real", self.path)
            elif name == "hardlink":
                os.link(self.path, self.path + ".x")
            elif name == "other_name":
                os.environ[CHECK_ENV] = shutil.copy(self.path, os.path.join(self.tdir, "other.json"))
            elif name == "linked_dir":
                os.symlink(self.tdir, os.path.join(self.base, "dirlink"))
                os.environ[CHECK_ENV] = os.path.join(self.base, "dirlink", CHECK_NAME)
            elif name == "code_sha":
                task = {"run_conditions": {"code_sha": ZERO}}
            elif name == "other_source":
                workdir = shutil.copytree(self.src, os.path.join(self.base, "copy"), symlinks=True)
            elif name == "changed_same_size":
                open(a, "w").write("print(2)\n")
            elif name == "deleted":
                os.remove(os.path.join(self.src, "sub", "b.txt"))
            elif name == "to_symlink":
                os.remove(a)
                os.symlink("sub/b.txt", a)
            elif name == "mode":
                os.chmod(a, 0o755)
            elif name == "link_target":
                os.remove(root)
                os.symlink("a.py", root)
            elif name == "no_experiment":
                edit(self.path, drop="experiment")
            elif name == "escape":
                edit(self.path, files={"../x": ["100644", ZERO]})
            elif name == "bad_mode":
                edit(self.path, files={"a.py": ["100666", ZERO]})
            else:
                edit(self.path, files={"a.py": ["100644", ZERO]})
            got[name] = refused(task, workdir)
        self.assertEqual(got, {name: True for name in cases})

    def test_result_cannot_be_supplied_through_the_contract_or_the_staging_folder(self):
        make_world(self)
        with open(os.path.join(self.src, "a.py"), "w", encoding="utf-8") as handle:
            handle.write("print(2)\n")  # 검증 뒤 실행 대상이 바뀐 상황
        blob = subprocess.run(["git", "hash-object", os.path.join(self.src, "a.py")], check=True, capture_output=True, text=True).stdout.strip()
        fake = json.load(open(self.path, encoding="utf-8"))
        fake["files"]["a.py"][1] = blob  # 바뀐 내용에 맞춘 위조 결과
        staging = os.path.join(self.base, "run", "out")
        os.makedirs(staging)
        spots = [os.path.join(staging, CHECK_NAME), os.path.join(self.base, "forged.json")]
        for spot in spots:
            json.dump(fake, open(spot, "w", encoding="utf-8"))
        task = {"run_conditions": {"code_sha": self.head, "config": {"code_check": spots[1], CHECK_ENV: spots[0]}, "command": ["x", spots[0]]},
                "code_check": spots[0], "inputs": {spots[1]: ZERO}}
        self.assertTrue(refused(task, self.src))  # 어댑터는 환경변수가 가리키는 runner의 파일만 읽는다(계약 필드의 경로·내용은 쓰이지 않는다)
        self.assertNotIn(blob, open(self.path, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
