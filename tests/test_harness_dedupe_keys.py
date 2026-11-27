"""2차 결함 G4: 실험·학습·평가의 논리 중복 키는 실제 실행 조건과 입력 내용만 본다.

- command는 입력을 자리표시자 {input:<inputs의 경로>}로 참조하고, 키는 자리표시자를 그 입력의 SHA로 바꾼 명령으로 만든다. 그래서 경로 철자·
  역할 이름(input_roles, 이제 설명)·세 유형 이름(experiment·training·evaluation은 한 부류)을 바꿔도 같은 키, 학습·검증 맞바꿈(같은 역할 두
  입력의 내용 맞바꿈 포함)은 다른 키다. command가 참조하지 않는 입력·없는 입력을 가리키는 자리표시자는 등록 거절이다.
- 표기 정규화(중복 쪽이 안전한 방향): python·python3·절대 경로 python 실행 파일은 같은 것, config 안 seed = seed 키(둘 다 있고 다르면
  거절), config 숫자 1 = 1.0. 명령의 숫자 토큰 0.10과 0.1은 이제 다르다(3차 결함 H2, 이전 기대: 같은 값. 근거와 나머지 숫자 규칙은
  test_harness_dedupe_numbers).
- 검사와 등록은 파일 잠금 안에서 한다: 두 프로세스가 같은 조건을 동시에 등록해도 하나만 들어간다.
- 실험 executor를 다른 유형 이름(deterministic 등)으로 감싼 executor 표는 쓰지 않는다. 실행 조건을 가진 비실험 유형은 거절한다.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from harness import contract as ct
from harness import queue, sandbox
from tests.test_harness_git_kit import CODE, git_source
from tests.test_harness_support import REPO, make_contract

T0 = 1_800_000_000.0
RACE = r'''
import sys, time
from harness import queue
from tests.test_harness_dedupe_keys import exp
root, src, risk, gate = sys.argv[1:5]
while time.time() < float(gate):
    pass
try:
    print(queue.enqueue(root, dict(exp(src), risk=risk), 1.0, source_root=src))
except queue.DuplicateTask as exc:
    print("DUP", exc.existing)
'''


def exp(src, task_type="experiment", files=None, command=None, **cond):
    """src 아래 files({경로: 내용})를 만들고 그 SHA로 만든 실험 계약. 기본 command는 학습·검증 입력을 자리표시자로 참조한다."""
    files = files or {"data/train.csv": "rows-1", "data/val.csv": "rows-2"}
    for rel, text in files.items():
        path = os.path.join(src, os.path.normpath(rel))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):  # 동시 등록 시험의 두 프로세스가 같은 파일을 다시 쓰지 않게(내용은 같다)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
    names = sorted(files)
    task = make_contract("x", task_type=task_type, inputs={rel: hashlib.sha256(files[rel].encode()).hexdigest() for rel in names})
    task["run_conditions"] = dict({"command": command or ["python", "train.py", "--lr", "0.1", "--train", "{input:%s}" % names[0],
                                                          "--val", "{input:%s}" % names[-1]], "code_sha": CODE}, **cond)
    return task


class DedupeKeyTest(unittest.TestCase):
    def setUp(self):
        self.root, self.src = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.src, True)
        git_source(self.src)  # code_sha는 source_root의 HEAD와 대조한다(3차 결함 H1)

    def test_registrant_labels_and_spelling_do_not_change_the_key(self):
        first = queue.enqueue(self.root, exp(self.src), T0, source_root=self.src)
        cmd = ["python", "train.py", "--lr", "0.1", "--train", "{input:data/train.csv}", "--val", "{input:data/val.csv}"]
        alias = {"./data/train.csv": "rows-1", "data/val.csv": "rows-2"}
        same = [exp(self.src, input_roles={"data/train.csv": "data", "data/val.csv": "data"}),  # 역할 이름만 다름
                exp(self.src, input_roles={"data/train.csv": "train", "data/val.csv": "val"}),
                exp(self.src, task_type="training"), exp(self.src, task_type="evaluation"),  # 세 유형은 한 부류
                exp(self.src, files=alias, command=["python", "train.py", "--lr", "0.1", "--train", "{input:./data/train.csv}",
                                                    "--val", "{input:data/val.csv}"]),  # 경로 철자
                exp(self.src, command=["python3"] + cmd[1:]), exp(self.src, command=["/usr/bin/python3"] + cmd[1:]),
                exp(self.src, command=cmd[:2] + ["--lr=0.1"] + cmd[4:])]
        for task in same:
            with self.assertRaises(queue.DuplicateTask, msg=task) as caught:
                queue.enqueue(self.root, task, T0 + 1, source_root=self.src)
            self.assertEqual(caught.exception.existing, first)
        trailing = queue.enqueue(self.root, exp(self.src, command=cmd[:3] + ["0.10"] + cmd[4:]), T0 + 1, source_root=self.src)
        self.assertNotEqual(trailing, first)  # 3차 H2: 소수점 끝 0은 문자열 그대로(이전 기대: first의 중복)
        seeded = queue.enqueue(self.root, exp(self.src, seed=3, config={"epochs": 1}), T0, source_root=self.src)
        for task in (exp(self.src, config={"epochs": 1, "seed": 3}), exp(self.src, seed=3, config={"epochs": 1.0})):
            with self.assertRaises(queue.DuplicateTask, msg=task) as caught:  # config 안 seed = seed 키, 1 = 1.0(중복 쪽)
                queue.enqueue(self.root, task, T0 + 1, source_root=self.src)
            self.assertEqual(caught.exception.existing, seeded)

    def test_real_swaps_and_differences_are_registered(self):
        same_role = {"data/a.csv": "X", "data/b.csv": "Y"}
        swapped = {"data/a.csv": "Y", "data/b.csv": "X"}  # 같은 역할 두 입력의 내용 맞바꿈: 명령은 경로로 읽으므로 실제로 다르다
        keys = [queue.enqueue(self.root, exp(self.src), T0, source_root=self.src),
                queue.enqueue(self.root, exp(self.src, command=["python", "train.py", "--lr", "0.1", "--train", "{input:data/val.csv}",
                                                                "--val", "{input:data/train.csv}"]), T0, source_root=self.src)]
        sub = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, sub, True)
        git_source(sub)
        keys.append(queue.enqueue(self.root, exp(sub, files=same_role), T0, source_root=sub))
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        git_source(other)
        keys.append(queue.enqueue(self.root, exp(other, files=swapped), T0, source_root=other))
        keys.append(queue.enqueue(self.root, exp(self.src, seed=1), T0, source_root=self.src))
        self.assertEqual(len(set(keys)), 5)

    def test_unreferenced_or_unknown_inputs_and_conditions_on_plain_types_are_refused(self):
        cmd = ["python", "train.py", "{input:data/train.csv}"]
        bad = [exp(self.src, command=cmd),  # data/val.csv를 command가 참조하지 않는다
               exp(self.src, command=cmd + ["{input:data/val.csv}", "{input:data/missing.csv}"]),  # 없는 입력
               exp(self.src, seed=1, config={"seed": 2}),  # seed가 두 곳에서 다르다
               dict(exp(self.src), task_type="deterministic")]  # 실행 조건을 가진 비실험 유형(실험을 감싸 다시 등록)
        for task in bad:
            with self.assertRaises(ct.ContractError, msg=task):
                queue.enqueue(self.root, task, T0, source_root=self.src)
        self.assertFalse(os.path.isdir(os.path.join(self.root, "tasks")))

    def test_concurrent_registration_of_the_same_conditions_admits_one(self):
        exp(self.src)
        for trial in range(5):
            root = tempfile.mkdtemp()
            gate = "%.3f" % (time.time() + 1.5)
            procs = [subprocess.Popen([sys.executable, "-c", RACE, root, self.src, risk, gate], cwd=REPO,
                                      stdout=subprocess.PIPE, text=True) for risk in ("low", "high")]
            outs = sorted(p.communicate(timeout=60)[0].strip() for p in procs)
            self.assertEqual(len([o for o in outs if o.startswith("DUP")]), 1, (trial, outs))
            self.assertEqual(len(os.listdir(os.path.join(root, "tasks"))), 1)

    def test_executor_table_that_aliases_an_experiment_executor_is_not_used(self):
        with self.assertRaises(sandbox.ChildError):
            sandbox.sandboxed(self.root, "tests.test_harness_boundary_kit:ALIASED")
        self.assertIn("experiment", sandbox.sandboxed(self.root, "tests.test_harness_boundary_kit:EXECUTORS"))


if __name__ == "__main__":
    unittest.main()
