"""논리 중복 키(작업 계약 2단계 R2). 실험·학습·평가 작업은 실제 실행 조건과 입력 내용(SHA)으로만 같은 작업인지 판정한다.

- 대상 유형 CONDITION_TYPES(임시 이름: experiment·training·evaluation. 5단계 작업 템플릿이 정하면 그 이름으로 맞춘다).
- run_conditions: 실행 조건 키 CONDITION_KEYS(command 필수: 비지 않은 문자열 목록, code_sha 필수: 소문자 16진 40·64자, config: dict,
  seed: 정수)와 설명 키 NOTE_KEYS(hypothesis_id·description: 키 계산에서 뺀다)만 받는다. 그 밖의 키는 조건인지 설명인지 판별할 수
  없으므로 등록을 거절한다(ContractError). run_conditions가 없는 대상 유형도 거절한다.
- 키 = sha256(task_type, 실행 조건, needs_llm, needs_vision, 입력 SHA 목록(경로 철자 무시, 정렬)). risk·retry_policy·escalation_level·
  expected_minutes·outputs·depends_on·설명 문구는 넣지 않는다. task_key·run_id는 그대로 둔다(이 키는 등록 거절에만 쓴다).
- 그 밖의 유형은 None(task_key가 정체성이다).
호출 깊이: find_duplicate → logical_key(말단) 1.
"""
import hashlib
import json
import os
import re

from .contract import ContractError
from .jsonio import read_json

CONDITION_TYPES = ("experiment", "training", "evaluation")
CONDITION_KEYS = ("command", "code_sha", "config", "seed")
NOTE_KEYS = ("hypothesis_id", "description")
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def logical_key(task):
    """대상 유형이면 논리 키(16진 64자), 아니면 None. 실행 조건을 판별할 수 없으면 ContractError."""
    if task.get("task_type") not in CONDITION_TYPES:
        return None
    cond = task.get("run_conditions")
    if not isinstance(cond, dict) or set(cond) - set(CONDITION_KEYS + NOTE_KEYS):
        raise ContractError("실험·학습·평가 작업은 run_conditions(%s, 설명 %s)가 필요하다" % (CONDITION_KEYS, NOTE_KEYS))
    command, code_sha = cond.get("command"), cond.get("code_sha")
    if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command) \
            or not isinstance(code_sha, str) or not _SHA.fullmatch(code_sha) \
            or not isinstance(cond.get("config", {}), dict) \
            or (cond.get("seed") is not None and (isinstance(cond["seed"], bool) or not isinstance(cond["seed"], int))):
        raise ContractError("run_conditions 형식 오류(command 문자열 목록·code_sha 16진·config dict·seed 정수)")
    body = {"task_type": task["task_type"], "conditions": {k: cond[k] for k in CONDITION_KEYS if k in cond},
            "needs_llm": task.get("needs_llm"), "needs_vision": task.get("needs_vision"),
            "inputs": sorted(task.get("inputs", {}).values())}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_duplicate(root, task, key):
    """task_key가 다른데 논리 키가 같은 등록 작업의 task_key(없으면 None). 상태와 무관하다(실패한 실험의 재등록 우회도 막는다)."""
    mine = logical_key(task)
    tasks_dir = os.path.join(root, "tasks")
    if mine is None or not os.path.isdir(tasks_dir):
        return None
    for other in sorted(os.listdir(tasks_dir)):
        if other == key:
            continue
        try:
            known = read_json(os.path.join(tasks_dir, other, "contract.json"))
            if isinstance(known, dict) and logical_key(known) == mine:
                return other
        except (OSError, ValueError, ContractError, AttributeError, TypeError):
            continue  # 깨진·옛 계약은 비교 대상이 아니다(상태 판정은 states가 한다)
    return None
