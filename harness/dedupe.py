"""논리 중복 키(작업 계약 2단계 R2, 검증 결함 F3 뒤). 실험·학습·평가 작업은 실제 실행 조건과 역할별 입력 내용(SHA)으로만 같은 작업인지 판정한다.

- 작업 유형은 코드의 고정 목록으로만 판별한다: CONDITION_TYPES(experiment·training·evaluation, 정확히 같은 이름)와 PLAIN_TYPES(Claude 권한 묶음
  유형 + deterministic). 목록에 없는 유형(대소문자·접미어 변형 포함)은 등록을 거절한다(fail-closed: 변형 이름으로 중복 검사를 빠져나갈 수 없다).
  새 Python 작업 유형은 이 목록에 코드로 추가해야 등록된다. 실행 조건(run_conditions)을 가진 PLAIN 유형도 거절한다.
- run_conditions(대상 유형은 필수): command(비지 않은 문자열 목록), code_sha(16진 40·64자, 대소문자 무시), input_roles({입력 경로: 역할},
  inputs와 같은 경로 집합, 역할은 INPUT_ROLES), config(dict, 생략·null = {}), seed(정수, 생략 = null)와 설명 키 NOTE_KEYS
  (hypothesis_id·description: 키 계산에서 뺀다). 그 밖의 키는 조건인지 설명인지 판별할 수 없어 거절한다. 입력 SHA는 16진 64자(대소문자 무시).
- 키 = sha256(task_type, 정규화한 실행 조건, needs_llm, needs_vision, (역할, 입력 SHA) 쌍 목록). 경로 철자는 빼고 역할은 넣는다:
  학습·검증 맞바꿈은 다른 조건, 같은 내용을 다른 경로로 적은 것은 같은 조건이다. 정규화: config 숫자 1.0 → 1(JSON 왕복), SHA 소문자,
  command의 --opt=value → --opt value, 경로 모양 토큰(/ 포함) normpath(./train.py → train.py).
  남는 한계: 인자 순서, python·python3·절대 경로 같은 실행 파일 별칭, 0.1·0.10 같은 문자열 숫자, 짧은 옵션 결합(-abc)은 다르게 본다.
- risk·retry_policy·escalation_level·expected_minutes·outputs·depends_on·설명 문구는 키에 넣지 않는다. task_key·run_id는 그대로 둔다.
- verify_inputs: 대상 유형의 입력을 source_root 아래 실제 파일과 대조한다(queue.enqueue·graph.register_missing 등록 때, runner가 executor 실행
  직전). 그 밖의 유형은 대조하지 않는다(Python 작업 입력의 원본 위치가 계약에 없다. Claude 작업은 claude_perm.stage_inputs가 실행 전에 대조).
호출 깊이: find_duplicate → logical_key → _command(말단) 2, verify_inputs → cas.sha_file(말단) 1.
"""
import hashlib
import json
import os
import re

from . import claude_perm
from .cas import sha_file
from .contract import ContractError
from .jsonio import read_json

CONDITION_TYPES = ("experiment", "training", "evaluation")
PLAIN_TYPES = frozenset(claude_perm.BUNDLE_OF) | {"deterministic"}  # 실행 조건 없이 등록하는 유형(고정 목록)
CONDITION_KEYS = ("command", "code_sha", "input_roles", "config", "seed")
NOTE_KEYS = ("hypothesis_id", "description")
INPUT_ROLES = ("train", "val", "test", "model", "config", "data")
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _command(command):
    """비교용 명령 표기(실제 실행 명령은 바꾸지 않는다): --opt=value는 두 토큰, 경로 모양 토큰은 normpath."""
    tokens = []
    for arg in command:
        parts = arg.split("=", 1) if arg.startswith("--") and "=" in arg else [arg]
        tokens += [os.path.normpath(p) if "/" in p and "://" not in p and not p.startswith("-") else p for p in parts]
    return tokens


def _number(text):
    """JSON 실수 문자열 → 정수로 같으면 int(1.0 → 1), 아니면 float."""
    value = float(text)
    return int(value) if value.is_integer() else value


def logical_key(task):
    """실험·학습·평가면 논리 키(16진 64자), 고정 목록의 그 밖 유형이면 None. 모르는 유형·판별할 수 없는 실행 조건은 ContractError."""
    kind, cond = task.get("task_type"), task.get("run_conditions")
    if kind in PLAIN_TYPES and cond is None:
        return None
    if kind not in CONDITION_TYPES:
        raise ContractError("등록 목록에 없는 작업 유형이거나 실행 조건을 가진 비실험 유형: %r" % (kind,))
    if not isinstance(cond, dict) or set(cond) - set(CONDITION_KEYS + NOTE_KEYS):
        raise ContractError("실험·학습·평가 작업은 run_conditions(%s, 설명 %s)가 필요하다" % (CONDITION_KEYS, NOTE_KEYS))
    command, code_sha, roles, inputs = cond.get("command"), cond.get("code_sha"), cond.get("input_roles"), task.get("inputs")
    config, seed = {} if cond.get("config") is None else cond["config"], cond.get("seed")
    if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command) \
            or not isinstance(code_sha, str) or not _SHA.fullmatch(code_sha.lower()) or not isinstance(config, dict) \
            or (seed is not None and (isinstance(seed, bool) or not isinstance(seed, int))):
        raise ContractError("run_conditions 형식 오류(command 문자열 목록·code_sha 16진·config dict·seed 정수)")
    if not isinstance(roles, dict) or not isinstance(inputs, dict) or set(roles) != set(inputs) \
            or not all(r in INPUT_ROLES for r in roles.values()) \
            or not all(isinstance(s, str) and _SHA256.fullmatch(s.lower()) for s in inputs.values()):
        raise ContractError("input_roles는 inputs의 모든 경로에 역할(%s)을 하나씩 정해야 하고 입력 SHA는 16진 64자다" % (INPUT_ROLES,))
    body = {"task_type": kind, "command": _command(command), "code_sha": code_sha.lower(),
            "config": json.loads(json.dumps(config, allow_nan=False), parse_float=_number), "seed": seed,
            "needs_llm": task.get("needs_llm"), "needs_vision": task.get("needs_vision"),
            "inputs": sorted([roles[rel], sha.lower()] for rel, sha in inputs.items())}
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


def verify_inputs(task, source_root):
    """실험·학습·평가 계약의 입력 {경로: sha256}이 source_root 아래 실제 파일(폴더 밖·없음·SHA 불일치 거절)과 같은지 본다. 다르면 ContractError."""
    if task.get("task_type") not in CONDITION_TYPES:
        return
    base = os.path.realpath(source_root)
    for rel, want in sorted(task["inputs"].items()):
        real = os.path.realpath(os.path.join(base, rel))
        if os.path.isabs(rel) or os.path.commonpath([base, real]) != base or not os.path.isfile(real):
            raise ContractError("입력이 원본 폴더 밖이거나 일반 파일이 아니다: %r" % rel)
        if sha_file(real) != str(want).lower():
            raise ContractError("입력 SHA가 실제 파일과 다르다: %r" % rel)
