"""B5-11 합성 종단 시험 공용 도구(시험 없음). 실험(가짜 executor) → 분석(가짜 claude) → 다음 선언(PLAN_GATE) → 학습 등록 → 평가 → 승격 판정을
실제 진입점 `python -m harness.supervisor` 한 번의 실행으로 돌린다. 실제 ./experiment·claude·학습·평가·모델·네트워크 호출 없음.
이 모듈은 sandbox 자식이 executor 표로 가져오므로 가져올 때 파일을 쓰지 않는다.
"""
import json
import os
import subprocess
import sys

from harness import contract as ct
from harness import plan_gate
from harness.jsonio import write_json
from tests import harness_plan_gate_kit as pg
from tests import harness_vs5_kit as vs5
from tests.test_harness_support import REPO
from tests.test_harness_vs3_entry import _fake_claude

EXECUTORS = {"experiment": pg.fake_experiment, "training": vs5.fake_train, "evaluation": vs5.fake_eval}  # 실험·학습·평가 모두 가짜


def chain(case, max_cycles=3):
    """합성 root에 사람이 쓰는 선언(대조 실험·학습·평가)만 두고 Supervisor를 한 번(프로세스 1개, max_cycles 회차) 실행한다.
    (root, src, 실행 요약 dict, 가짜 claude 로그, {"e1","train","eval"} 작업 키)."""
    root, src, head = pg.world(case)
    control, train = pg.control(head), vs5.training(head)
    ev = vs5.evaluation(head, ct.task_key(train))
    for hid in ("H1", "H-next"):
        pg.seed(src, hid)  # 가짜 실험 executor가 옮길 동결 기록(./experiment가 남기는 모양)
    write_json(os.path.join(root, "supervisor", "declared.json"), {ct.task_key(t): t for t in (control, train, ev)})
    claude, log = _fake_claude(case, [{"do": "success", "files": {plan_gate.NEXT_PLAN: json.dumps(pg.proposal(control))}}])
    done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--claude-bin", claude, "--executors",
                           "tests.harness_b5_e2e_kit:EXECUTORS", "--source-root", src, "--max-cycles", str(max_cycles), "--poll", "0"],
                          cwd=REPO, capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-1500:]
    keys = {"e1": ct.task_key(control), "train": ct.task_key(train), "eval": ct.task_key(ev)}
    return root, src, json.loads(done.stdout.strip().split("\n")[-1]), log, keys
