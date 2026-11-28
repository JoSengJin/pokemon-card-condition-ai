"""VS5 시험 공용 도구(시험 없음) 2/2. 합성 world에 학습·평가 작업을 올려 VERIFIED까지 돌리고, 적용기 진입점을 별도 프로세스로 부른다."""
import functools
import json
import os
import subprocess
import sys

from harness import contract as ct
from harness import queue, runner
from harness.jsonio import read_json, write_json
from tests import harness_vs5_kit as kit
from tests.harness_plan_gate_kit import NOW, world  # noqa: F401 — 시험이 run.world로 쓴다

def verified_pair(case, variant="better", **eval_over):
    """합성 world에 학습·평가 작업을 등록하고 가짜 executor로 VERIFIED까지 돌린다(sandbox 없는 drain). (root, src, head, 학습 key, 평가 key)."""
    root, src, head = world(case)
    train = kit.training(head)
    tkey = queue.enqueue(root, train, NOW, source_root=src)
    ekey = queue.enqueue(root, kit.evaluation(head, tkey, variant, **eval_over), NOW, source_root=src)
    runner.drain(root, kit.EXECUTORS, now_fn=functools.partial(float, NOW), source_root=src)
    return root, src, head, tkey, ekey


def run_all(case):
    """case.root에 declared.json의 작업을 모두 등록하고 가짜 executor로 VERIFIED까지 돌린다(sandbox 없는 drain, 적용 전)."""
    for task in sorted(read_json(os.path.join(case.root, "supervisor", "declared.json")).values(), key=lambda t: t["task_type"] != "training"):
        queue.enqueue(case.root, task, NOW, source_root=case.src)
    runner.drain(case.root, kit.EXECUTORS, now_fn=functools.partial(float, NOW), source_root=case.src)


def declare(root, *tasks):
    """사람이 한 번 쓰는 선언 파일 root/supervisor/declared.json."""
    write_json(os.path.join(root, "supervisor", "declared.json"), {ct.task_key(t): t for t in tasks})


def apply_all(root):
    """적용기 진입점 `python -m harness.apply_main <root>`을 별도 프로세스로 한 번 돌려 결과 목록을 돌려준다(Supervisor가 부르는 방식 그대로)."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    done = subprocess.run([sys.executable, "-m", "harness.apply_main", root], cwd=repo, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise AssertionError(done.stderr[-1500:])
    return json.loads(done.stdout.strip().split("\n")[-1])
