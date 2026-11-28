"""적용기 진입점(VS5). VERIFIED 학습 작업(B5-7 apply_train)과 VERIFIED 평가 작업(B5-10 apply_promote)의 결과를 하네스 상태에 반영한다.
Supervisor가 회차마다 `pending`이 비어 있지 않을 때 `python -m harness.apply_main <root>`를 별도 프로세스로 한 번 부른다(_python과 같은 방식).
별도 프로세스인 이유: apply_train.apply·apply_promote.apply가 각각 호출 깊이 4라 어떤 함수 안에서 부르면 한도(4)를 넘는다. 그래서 반복은 함수가 아니라 아래
`__main__` 블록이 한다(블록은 깊이에 더하지 않는다). 출력 마지막 줄 = 결과 목록 JSON [{"kind": "train"|"promote", "task_key", "ok", ...}].
순서는 학습 먼저, 평가 나중이다(평가 판정은 학습 적용 기록이 필요하다). 승격은 하지 않는다. 정지 상태면 두 적용기가 모두 halted로 거절한다.
pending은 읽기만 하며 적용 기록이 없는 학습·평가 작업만 해시를 계산한다(적용된 작업은 계약 JSON만 읽는다).
적용 대상: 학습 = outputs에 weights.bin·eval.json, 평가 = outputs에 rows.json이고 config.promotion이 dict. 그 밖의 학습·평가 작업은 건드리지 않는다.
영구 거절 작업(계약 형식 오류 등)은 회차마다 이 프로세스가 다시 뜬다(알림은 Supervisor가 같은 사유를 한 번만 남긴다). 보류: 거절 기록으로 건너뛰기.
"""
import json
import os
import sys
import time

from . import apply_promote, apply_train, contract as ct, states
from .jsonio import read_json

RECORDS = {"train": apply_train.APPLIED, "promote": apply_promote.VERDICTS}


def _kind(task):
    """계약이 적용 대상이면 "train"|"promote", 아니면 None. 말단."""
    outputs, cond = task.get("outputs"), task.get("run_conditions")
    config = cond.get("config") if isinstance(cond, dict) else None
    if task.get("task_type") == "training" and {apply_train.WEIGHTS, apply_train.EVAL} <= set(outputs or ()):
        return "train"
    if task.get("task_type") == "evaluation" and apply_promote.ROWS in (outputs or ()) and isinstance(config, dict) \
            and isinstance(config.get("promotion"), dict):
        return "promote"
    return None


def pending(root):
    """[(종류, task_key)]: 적용 기록이 없는 VERIFIED 학습(train)이 먼저, 평가(promote)가 나중(각각 task_key 순). 읽기만 한다."""
    tasks = os.path.join(root, "tasks")
    found = []
    for key in sorted(os.listdir(tasks)) if os.path.isdir(tasks) else []:
        try:
            kind = _kind(read_json(os.path.join(tasks, ct.check_key(key), "contract.json"), {}) or {})
        except (ValueError, AttributeError, OSError, ct.ContractError):
            continue  # 작업 폴더가 아니거나 읽을 수 없는 계약(그 작업은 runner·claim이 따로 다룬다)
        if kind is None or os.path.exists(os.path.join(root, RECORDS[kind], key + ".json")):
            continue
        info = states.facts(os.path.join(tasks, key))
        if states.state_of(info, False) == states.VERIFIED:
            found.append((kind, key))
    return sorted(found, key=lambda item: (item[0] != "train", item[1]))


if __name__ == "__main__":  # 진입점(깊이에 더하지 않는다): python -m harness.apply_main <root>
    ROOT, RESULTS = os.path.abspath(sys.argv[1]), []
    for KIND, KEY in pending(ROOT):
        RESULTS.append(dict((apply_train.apply if KIND == "train" else apply_promote.apply)(ROOT, KEY, time.time()), kind=KIND))
    print(json.dumps(RESULTS, sort_keys=True, ensure_ascii=False), flush=True)
