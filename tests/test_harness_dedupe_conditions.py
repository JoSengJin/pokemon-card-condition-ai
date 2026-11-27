"""검증 결함 F3(+F12 일부): 실험·학습·평가의 논리 중복 판정.

- 작업 유형은 코드의 고정 목록으로만 판별한다. 모르는 유형·변형 이름(대소문자·접미어)은 run_conditions가 있든 없든 등록 거절이라
  중복 검사를 빠져나갈 수 없다. 실행 조건을 가진 비실험 유형도 거절한다.
- 같은 조건의 다른 표기(config 생략·{}·null, seed 생략·null, 1과 1.0, SHA 대소문자, ./train.py, --lr=0.1, 입력 파일 경로 철자)는 중복,
  실제로 다른 조건(학습·검증 맞바꿈: 명령의 자리표시자 자리가 바뀜, 입력 내용, needs_vision, 입력 추가)은 등록된다(2차 G4 뒤 기준은
  test_harness_dedupe_keys).
- 입력 SHA는 형식을 검사하고 등록할 때와 executor 실행 직전에 실제 파일과 대조한다(다르면 등록 거절·결정적 실패, executor 실행 0).
"""
import hashlib
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import contract as ct
from harness import graph, queue, runner, states
from tests.test_harness_support import make_contract

T0 = 1_800_000_000.0
CODE = "0123456789abcdef0123456789abcdef01234567"
FILES = {"data/train.csv": "train-rows", "data/val.csv": "val-rows", "copy/train_copy.csv": "train-rows", "data/other.csv": "other"}


def _source(case):
    """입력 원본 폴더와 {경로: sha256}."""
    src = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, src, True)
    for rel, text in FILES.items():
        os.makedirs(os.path.dirname(os.path.join(src, rel)), exist_ok=True)
        with open(os.path.join(src, rel), "w", encoding="utf-8") as handle:
            handle.write(text)
    return src, {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in FILES.items()}


def _exp(sha, roles=None, **cond):
    """학습 data/train.csv·검증 data/val.csv를 쓰는 실험 계약. roles: {경로: 역할}(기본 train·val). command(기본 python train.py --lr 0.1)
    뒤에 역할 순서(train·val·test)로 --<역할> {input:<경로>}를 붙인다(2차 결함 G4: 키는 자리표시자를 입력 SHA로 바꾼 명령으로 정하고
    input_roles는 설명이다. 그래서 역할 맞바꿈은 명령의 자리가 바뀌어 다른 조건이다)."""
    roles = roles or {"data/train.csv": "train", "data/val.csv": "val"}
    task = make_contract("x", task_type="experiment", inputs={rel: sha[rel] for rel in roles})
    order = ("train", "val", "test")
    refs = [t for role in order for rel, mine in sorted(roles.items()) if mine == role for t in ("--" + role, "{input:%s}" % rel)]
    base = cond.pop("command", ["python", "train.py", "--lr", "0.1"])
    task["run_conditions"] = dict({"command": base + refs, "code_sha": CODE, "input_roles": roles}, **cond)
    return task


class DedupeConditionTest(unittest.TestCase):
    def test_unknown_or_variant_task_types_cannot_bypass_the_duplicate_check(self):
        root, sha = tempfile.mkdtemp(), {rel: "ab" * 32 for rel in FILES}
        for name in ("Experiment", "experiment_run", "evaluation_v2", "training-job", "job42"):
            for keep in (True, False):  # 실행 조건을 붙여도, 빼도
                task = dict(_exp(sha), task_type=name)
                if not keep:
                    task.pop("run_conditions")
                with self.assertRaises(ct.ContractError, msg=name):
                    queue.enqueue(root, task, T0)
                got = graph.register_missing(root, {ct.task_key(task): task}, T0)  # 2차 G5: 그 선언만 거절(이전 기대: ContractError)
                self.assertIn("ContractError", got["rejected"][ct.task_key(task)], name)
        plain = dict(make_contract("p", task_type="misanalysis_general"), run_conditions=_exp(sha)["run_conditions"])
        with self.assertRaises(ct.ContractError):  # 실행 조건을 가진 비실험 유형(조건인지 판별 불가)
            queue.enqueue(root, plain, T0)
        self.assertFalse(os.path.isdir(os.path.join(root, "tasks")))

    def test_same_conditions_written_differently_are_duplicates(self):
        root, (src, sha) = tempfile.mkdtemp(), _source(self)
        first = queue.enqueue(root, _exp(sha), T0, source_root=src)
        lr1 = queue.enqueue(root, _exp(sha, config={"lr": 1}), T0, source_root=src)
        upper = {rel: value.upper() for rel, value in sha.items()}
        cases = [(_exp(sha, config={}), first), (_exp(sha, config=None), first), (_exp(sha, seed=None), first),
                 (_exp(upper), first), (_exp(sha, code_sha=CODE.upper()), first),
                 (_exp(sha, command=["python", "./train.py", "--lr", "0.1"]), first),
                 (_exp(sha, command=["python", "train.py", "--lr=0.1"]), first),
                 (_exp(sha, roles={"copy/train_copy.csv": "train", "data/val.csv": "val"}), first),  # 경로 철자만 다름(같은 내용)
                 (_exp(dict(sha, **{"./data/train.csv": sha["data/train.csv"]}),
                       roles={"./data/train.csv": "train", "data/val.csv": "val"}), first),
                 (_exp(sha, hypothesis_id="H-9", description="다른 설명"), first),
                 (_exp(sha, config={"lr": 1.0}), lr1)]
        for task, existing in cases:
            with self.assertRaises(queue.DuplicateTask, msg=task["run_conditions"]) as caught:
                queue.enqueue(root, task, T0 + 1, source_root=src)
            self.assertEqual(caught.exception.existing, existing)

    def test_real_differences_are_registered(self):
        root, (src, sha) = tempfile.mkdtemp(), _source(self)
        keys = [queue.enqueue(root, _exp(sha), T0, source_root=src)]
        swapped = _exp(sha, roles={"data/train.csv": "val", "data/val.csv": "train"})  # 학습·검증 역할 맞바꿈
        other_input = _exp(sha, roles={"data/other.csv": "train", "data/val.csv": "val"})  # 입력 SHA만 다름(F12)
        more = _exp(sha, roles={"data/train.csv": "train", "data/val.csv": "val", "data/other.csv": "test"})
        for task in (swapped, other_input, more, dict(_exp(sha), needs_vision=True), _exp(sha, seed=7)):
            keys.append(queue.enqueue(root, task, T0, source_root=src))
        self.assertEqual(len(set(keys)), 6)

    def test_input_sha_is_checked_against_files_at_registration_and_right_before_execution(self):
        root, (src, sha) = tempfile.mkdtemp(), _source(self)
        broken = [dict(sha, **{"data/train.csv": "not-a-sha"}), dict(sha, **{"data/train.csv": sha["data/other.csv"]})]
        for bad in broken:
            with self.assertRaises(ct.ContractError):  # 형식 오류, 실제 파일과 다른 SHA
                queue.enqueue(root, _exp(bad), T0, source_root=src)
        for roles in ({"missing.csv": "train"}, {"../outside.csv": "train"}, {"/etc/hosts": "train"}):
            with self.assertRaises(ct.ContractError):  # 없는 파일·원본 폴더 밖
                queue.enqueue(root, _exp(dict(sha, **{r: "ab" * 32 for r in roles}), roles=roles), T0, source_root=src)
        key = queue.enqueue(root, _exp(sha), T0, source_root=src)
        with open(os.path.join(src, "data", "train.csv"), "a", encoding="utf-8") as handle:
            handle.write("changed after registration")
        executor = mock.Mock(return_value=["result.txt"])
        summary = runner.drain(root, {"experiment": executor}, max_tasks=1, source_root=src)
        self.assertEqual((executor.call_count, summary["failed"][0][1]), (0, "deterministic"))
        task_dir = os.path.join(root, "tasks", key)
        self.assertEqual(states.state_of(states.facts(task_dir), False), states.FAILED)
        self.assertIn("SHA", states.failures(task_dir)[0]["error"])


if __name__ == "__main__":
    unittest.main()
