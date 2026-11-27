"""논리 중복 키(작업 계약 2단계 R2, 검증 결함 F3·2차 결함 G4 뒤). 실험·학습·평가 작업은 실제 실행 조건과 입력 내용(SHA)으로만 같은 작업인지 판정한다.

- 작업 유형은 코드의 고정 목록으로만 판별한다: CONDITION_TYPES(experiment·training·evaluation, 정확히 같은 이름)와 PLAIN_TYPES(Claude 권한 묶음
  유형 + deterministic). 목록에 없는 유형(대소문자·접미어 변형 포함)은 등록을 거절한다(fail-closed: 변형 이름으로 중복 검사를 빠져나갈 수 없다).
  새 Python 작업 유형은 이 목록에 코드로 추가해야 등록된다. 실행 조건(run_conditions)을 가진 PLAIN 유형도 거절한다(실험을 deterministic으로
  감싸 실행 조건 없이 다시 등록하는 경로. 실험 executor를 다른 유형 이름에도 등록한 executor 표는 sandbox_child가 거절한다).
- run_conditions(대상 유형은 필수): command(비지 않은 문자열 목록), code_sha(16진 40·64자, 대소문자 무시. 3차 결함 H1: 등록 때와 executor
  실행 직전에 source_root의 git HEAD와 같고 추적 파일 변경이 없어야 한다 = verify_code, 다르거나 판별할 수 없으면 거절), config(dict, 생략·null = {}),
  seed(정수, 생략 = null)와 설명 키 NOTE_KEYS(hypothesis_id·description·input_roles: 키 계산에서 뺀다. input_roles는 등록자가 붙인 역할 표시라
  실행에 쓰이지 않는다). 그 밖의 키는 조건인지 설명인지 판별할 수 없어 거절한다. 입력 SHA는 16진 64자(대소문자 무시).
- 입력 참조(2차 G4): command는 입력을 자리표시자 {input:<inputs의 경로>}로 참조한다. 키는 자리표시자를 그 입력의 SHA로 바꾼 명령으로 만든다.
  그래서 경로 철자·역할 이름·세 유형 이름이 달라도 같은 키이고, 학습·검증 맞바꿈(같은 역할 두 입력의 내용 맞바꿈 포함)은 명령의 자리가
  달라 다른 키다. command가 참조하지 않는 입력과 없는 입력을 가리키는 자리표시자는 거절한다(참조하지 않은 입력이 실행에 어떻게 쓰이는지
  판별할 수 없어 키를 정할 수 없다). executor·실행기는 자리표시자를 HARNESS_INPUT_DIR 아래 같은 상대 경로(SHA를 확인한 사본)로 바꿔 쓴다.
- 키 = sha256("condition"(세 유형 한 부류), 정규화한 command·code_sha(= 대조한 HEAD)·config·seed, needs_llm, needs_llm=true일 때만 needs_vision).
  needs_llm=false면 needs_vision은 실행에 쓰이지 않으므로 키에서 빼고 true는 거절한다(3차 결함 H1: 그 값만 뒤집어 다시 등록하는 우회). 정규화는 중복 쪽(같다고 보는 쪽)이
  안전한 방향만 한다: --opt=value → 두 토큰, 경로 모양 토큰(/ 포함) normpath, 저장소(claude_perm.REPO) 아래 절대 경로 → 상대 경로, 첫 토큰의
  python 실행 파일 별칭(python·python3·python3.12·절대 경로) → python, 숫자 토큰(1·1.0·0.10) → 같은 값, config 안 seed → seed 키(둘 다 있고
  다르면 거절), config 숫자 1.0 → 1(JSON 왕복). config 1과 1.0을 같게 보는 이유: 대부분의 실행 코드가 수치로 같게 쓰고, 같다고 봐서 생기는
  손해는 등록 거절(DuplicateTask가 기존 작업을 알려 주고 사람이 고칠 수 있음)이지만 다르다고 봐서 생기는 손해는 같은 실험의 중복 실행이다.
  남는 한계(판별할 수 없는 표기 차이): 인자 순서, 짧은 옵션 결합(-abc), 저장소 밖 절대 경로 철자, config 안의 경로 문자열 철자, 명령 안
  seed 인자(--seed 1)와 seed 키, 그 밖의 실행 파일 별칭, 인터프리터 옵션(python -u 등), 실행에 쓰이지 않는 config 키는 다르게 본다(같은
  실험이 중복 등록될 수 있다, 3차 H3).
- risk·retry_policy·escalation_level·expected_minutes·outputs·depends_on·설명 문구는 키에 넣지 않는다. task_key·run_id는 그대로 둔다.
- verify_inputs: 대상 유형의 입력을 source_root 아래 실제 파일과 대조한다(queue.enqueue·graph.register_missing 등록 때). 실행 직전에는 runner가
  claude_perm.stage_inputs로 사본을 만들며 다시 대조한다. 그 밖의 유형은 대조하지 않는다(Python 작업 입력의 원본 위치가 계약에 없다).
- 등록(검사 + 저장)은 root의 contract.ENQUEUE_LOCK 파일 잠금 안에서 한다(queue.enqueue·graph.register_missing): 동시 등록이 둘 다 통과하지 않게.
호출 깊이: find_duplicate → logical_key → _command(말단) 2, verify_inputs → verify_code(말단)·cas.sha_file(말단) 1.
"""
import hashlib
import json
import os
import re
import subprocess

from . import claude_perm
from .cas import sha_file
from .contract import ContractError
from .jsonio import read_json

CONDITION_TYPES = ("experiment", "training", "evaluation")
PLAIN_TYPES = frozenset(claude_perm.BUNDLE_OF) | {"deterministic"}  # 실행 조건 없이 등록하는 유형(고정 목록)
CONDITION_KEYS = ("command", "code_sha", "config", "seed")
NOTE_KEYS = ("hypothesis_id", "description", "input_roles")
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PLACEHOLDER = re.compile(r"\{input:([^{}]+)\}")
_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_PYTHON = re.compile(r"python(?:\d+(?:\.\d+)*)?")


def _command(command, inputs):
    """비교용 명령 표기(실제 실행 명령은 바꾸지 않는다). inputs: {정규화 경로: sha}. 자리표시자 → {sha:<입력 SHA>}, 위 정규화.
    참조하지 않은 입력·없는 입력 자리표시자는 ContractError."""
    tokens, used = [], set()
    for index, arg in enumerate(command):
        for part in arg.split("=", 1) if arg.startswith("--") and "=" in arg else [arg]:
            pieces = _PLACEHOLDER.split(part)  # [글자, 경로, 글자, 경로, ...]
            if len(pieces) > 1:
                names = [os.path.normpath(p) for p in pieces[1::2]]
                if any(n not in inputs for n in names):
                    raise ContractError("command의 자리표시자가 inputs에 없는 입력을 가리킨다: %r" % part)
                used.update(names)
                part = "".join(p if i % 2 == 0 else "{sha:%s}" % inputs[os.path.normpath(p)] for i, p in enumerate(pieces))
            elif index == 0 and _PYTHON.fullmatch(os.path.basename(part)):
                part = "python"
            elif _NUMBER.fullmatch(part):
                value = float(part)
                part = repr(int(value)) if value.is_integer() and abs(value) < 1e15 else repr(value)
            elif os.path.isabs(part) and os.path.commonpath([claude_perm.REPO, os.path.normpath(part)]) == claude_perm.REPO:
                part = os.path.relpath(os.path.normpath(part), claude_perm.REPO)
            elif "/" in part and "://" not in part and not part.startswith("-"):
                part = os.path.normpath(part)
            tokens.append(part)
    if used != set(inputs):
        raise ContractError("command가 참조하지 않는 입력이 있다(자리표시자 {input:<경로>}로 참조): %s" % sorted(set(inputs) - used))
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
    command, code_sha, inputs = cond.get("command"), cond.get("code_sha"), task.get("inputs")
    config, seed = {} if cond.get("config") is None else cond["config"], cond.get("seed")
    if isinstance(config, dict) and "seed" in config:  # config 안 seed = seed 키(둘 다 있고 다르면 판별 불가)
        if seed is not None and config["seed"] != seed:
            raise ContractError("seed가 config와 seed 키에 서로 다르게 있다")
        seed, config = config["seed"], {k: v for k, v in config.items() if k != "seed"}
    if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command) \
            or not isinstance(code_sha, str) or not _SHA.fullmatch(code_sha.lower()) or not isinstance(config, dict) \
            or (seed is not None and (isinstance(seed, bool) or not isinstance(seed, int))):
        raise ContractError("run_conditions 형식 오류(command 문자열 목록·code_sha 16진·config dict·seed 정수)")
    if not isinstance(inputs, dict) or not all(isinstance(s, str) and _SHA256.fullmatch(s.lower()) for s in inputs.values()):
        raise ContractError("실험·학습·평가 입력 SHA는 16진 64자다")
    paths = {os.path.normpath(rel): sha.lower() for rel, sha in inputs.items()}
    if len(paths) != len(inputs):
        raise ContractError("inputs에 철자만 다른 같은 경로가 있다: %s" % sorted(inputs))
    if not task.get("needs_llm") and task.get("needs_vision") is True:  # 실행에 쓰이지 않는 값(3차 H1: 뒤집어 다시 등록하는 우회)
        raise ContractError("needs_llm=false인 실험·학습·평가는 needs_vision=true일 수 없다")
    body = {"class": "condition", "command": _command(command, paths), "code_sha": code_sha.lower(),
            "config": json.loads(json.dumps(config, allow_nan=False), parse_float=_number), "seed": seed,
            "needs_llm": task.get("needs_llm")}
    if task.get("needs_llm"):  # LLM을 쓰는 경우에만 needs_vision이 실행 조건이다
        body["needs_vision"] = task.get("needs_vision")
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


def verify_code(task, source_root):
    """실험·학습·평가 계약의 run_conditions.code_sha가 source_root의 실제 코드인지 본다(3차 결함 H1): source_root가 git 저장소의 최상위이고,
    `git rev-parse HEAD`(소문자)와 같고, 작업 트리에 추적 파일 변경(스테이징 포함)이 없어야 한다. 추적하지 않는 파일(입력 자료)은 보지 않는다
    (입력은 SHA로 따로 대조한다). 다르거나 git 저장소가 아니거나 git을 실행할 수 없으면 ContractError(fail-closed). 정규화한 HEAD를 돌려준다.
    git은 사용자 환경의 GIT_* 변수를 빼고, 선택적 잠금(index 갱신)·fsmonitor 없이 읽기만 한다. 그 밖의 유형은 None(대조하지 않는다)."""
    if task.get("task_type") not in CONDITION_TYPES:
        return None
    want = (task.get("run_conditions") or {}).get("code_sha")
    env = dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, GIT_OPTIONAL_LOCKS="0")
    base = ["git", "-c", "core.fsmonitor=false", "-C", os.path.realpath(source_root)]
    try:
        top = subprocess.run(base + ["rev-parse", "--show-toplevel", "--verify", "HEAD"], env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=120, check=False)
        dirty = subprocess.run(base + ["status", "--porcelain", "--untracked-files=no"], env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError("code_sha를 판별할 수 없다(git 실행 실패): %s" % exc)
    lines = top.stdout.split("\n")
    if top.returncode != 0 or dirty.returncode != 0 or len(lines) < 2 \
            or os.path.realpath(lines[0]) != os.path.realpath(source_root):
        raise ContractError("code_sha를 판별할 수 없다(source_root가 git 저장소 최상위가 아니거나 HEAD를 읽지 못함): %s" % source_root)
    head = lines[1].strip().lower()
    if not _SHA.fullmatch(head) or not isinstance(want, str) or want.lower() != head:
        raise ContractError("code_sha가 source_root의 HEAD(%s)와 다르다: %r" % (head, want))
    if dirty.stdout.strip():
        raise ContractError("code_sha를 판별할 수 없다(source_root 작업 트리에 추적 파일 변경이 있다)")
    return head


def verify_inputs(task, source_root):
    """실험·학습·평가 계약의 code_sha(verify_code)와 입력 {경로: sha256}이 source_root 아래 실제 코드·파일(폴더 밖·없음·SHA 불일치 거절)과
    같은지 본다. 다르면 ContractError."""
    if task.get("task_type") not in CONDITION_TYPES:
        return
    verify_code(task, source_root)
    base = os.path.realpath(source_root)
    for rel, want in sorted(task["inputs"].items()):
        real = os.path.realpath(os.path.join(base, rel))
        if os.path.isabs(rel) or os.path.commonpath([base, real]) != base or not os.path.isfile(real):
            raise ContractError("입력이 원본 폴더 밖이거나 일반 파일이 아니다: %r" % rel)
        if sha_file(real) != str(want).lower():
            raise ContractError("입력 SHA가 실제 파일과 다르다: %r" % rel)
