"""VS5 시험 공용 도구(시험 없음) 1/2. 합성 학습·평가 계약과 가짜 executor(실행·진입점 도구는 harness_vs5_run). 실제 학습·평가·모델·네트워크를 부르지 않는다.

가짜 학습 executor는 가중치 바이트와 dev 평가 기록을, 가짜 평가 executor는 합성 구역 행(rows.json)을 out/에 쓸 뿐이다. 합성이라
모델 성능 근거가 아니다. 이 모듈은 sandbox 자식이 executor 표로 가져오므로 가져올 때 파일을 쓰지 않는다.
"""
import os

from harness.jsonio import write_json
from tests.test_harness_scoring_support import make_rows

FA = {"fa": range(90, 100)}
BASE = dict(miss=range(0, 40), **FA)
SETTING = {"noise_rate": 0.1, "direction_min_fraction": 0.9, "min_defect_cards": 10, "min_valid_fraction": 0.9,
           "replicates": 200, "trials": 100, "seed": 0}  # 시험용 값(승인된 사전 등록 수치가 아니다)
EVAL = {"layer": "dev", "denominator": "zones:n=400", "seal_version": "none", "metrics": {"miss": 0.1}}


def _base(kind, outputs, depends, head, seed, config):
    return {"task_type": kind, "inputs": {}, "outputs": outputs, "depends_on": depends, "needs_llm": False, "needs_vision": False,
            "risk": "high", "retry_policy": {}, "escalation_level": 0,
            "run_conditions": {"command": ["python", kind + ".py"], "code_sha": head, "seed": seed, "config": config}}


def training(head, lr=0.01):
    return _base("training", ["weights.bin", "eval.json"], [], head, 3, {"lr": lr})


def evaluation(head, train_key, variant="better", promotion=None, candidate_of=True, depends=True):
    """학습 작업 train_key가 낸 모델을 채점하는 평가 계약. 사전 등록 수치는 config.promotion(계약 SHA에 묶인다)."""
    config = {"promotion": dict(SETTING if promotion is None else promotion), "variant": variant}
    if candidate_of:
        config["candidate_of"] = train_key
    return _base("evaluation", ["rows.json"], [train_key] if depends else [], head, 4, config)


def fake_train(task, out_dir):
    lr = task["run_conditions"]["config"]["lr"]
    with open(os.path.join(out_dir, "weights.bin"), "wb") as handle:
        handle.write(("weights-lr=%s" % lr).encode())
    write_json(os.path.join(out_dir, "eval.json"), EVAL)
    return ["weights.bin", "eval.json"]


def fake_eval(task, out_dir):
    variant = task["run_conditions"]["config"]["variant"]
    cand = dict(miss=range(0, 10), **FA) if variant == "better" else dict(BASE, abs_normal=range(100))
    rows = make_rows(BASE, cand, uncertain=range(0, 5))
    if variant == "sealed":
        rows[0]["eval_tier"] = "sealed"
    write_json(os.path.join(out_dir, "rows.json"), rows)
    return ["rows.json"]


EXECUTORS = {"training": fake_train, "evaluation": fake_eval}
