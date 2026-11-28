"""사람 해제·재개(B6-5)와 해제용 훅 문구(B6-6). 사람이 직접 실행하는 진입점이며 Supervisor·다른 하네스 코드는 이 파일을 부르지 않는다(시험이 ast로 확인).

    1단계 python -m harness.control_release --root R --target T            근거 출력 + 1회용 확인 코드(표준 오류)
    2단계 python -m harness.control_release --root R --target T --code C --reason 사유 --confirm
    훅    "재개 T"(1단계: 종료 코드 2 + 표준 오류) → "재개 T C"(2단계)

- 대상은 이름 하나: 운영 조건(DONE 제외: pre-b6 결정 7) 또는 interrupts:<작업 키>·holder:<작업 키>(unlock). 한 번에 하나, "전부 해제" 없음.
  awaiting.json·blocked Claude 작업은 대상이 아니다(결정 5: 상태 조회 표시 + 수동 절차).
- 문구·터미널 입력만으로 풀지 않는다(B6 결정 2): 1단계가 만든 코드(6자리, TTL_S, 1회, 대상에 묶임, MAX_TRIES번 틀리면 폐기, 새로 받으면 이전 것
  무효)가 2단계에 맞아야 푼다. 파일에는 sha256(salt+코드)만 둔다. 훅 1단계는 종료 코드 2 + stderr로 코드를 보인다: 설치본 문자열 기준 stderr는
  사용자에게만 보이고 프롬프트가 지워져 모델은 요청도 코드도 보지 못한다(실설치·폰 화면은 미검증. 안 보이면 못 푼다 = 중단 유지).
- 이것은 사용자 인증이 아니다. 막는 것: 지난 문구·코드 재생, 오입력, 다른 대상의 코드, sandbox 안 executor(쓰기 거절), A묶음 Claude(명령 실행
  도구 없음, 쓰는 산출물 폴더를 여기서 읽지 않음). 못 막는 것: sandbox 밖 같은 macOS 사용자 프로세스(대화형 Claude·Codex·셸)는 1단계를 직접
  실행해 코드를 보거나 함수·상태 파일을 직접 고칠 수 있다(sandbox.py 한계와 같다). 그래서 장부에는 경로(hook·terminal)만 남기고 인증됐다고 적지 않는다.
- 자동 재개와 구분: 한도 조건의 자동 해제는 Supervisor의 opstate.clear_auto(소진 아닌 것)뿐이다. 사람이 한도 조건을 풀어도 시각 미상 한도
  시도 횟수는 그대로 둔다(결정 4: 초기화는 사람이 기록 파일을 지우는 별도 절차). 실행 중 작업은 끊지 않으므로 해제는 새 작업 시작만 다시 허용한다(결정 3).
- 해제 결과는 상태를 다시 읽어 확인한 사실만 말한다. 손상된 운영 상태는 풀지 않는다(opstate 규칙: 덮어쓰지 않음, 수동 복구).
호출 깊이(시작 함수 answer·request·from_prompt는 __main__ 블록과 훅 진입점이 직접 부른다): answer → opstate.clear_by_user → _clear → load →
read_json 4, request → evidence → opstate.load → read_json 3.
"""
import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import unicodedata

from . import claude_job, ledger, opstate, status, unlock
from . import contract as ct
from .jsonio import read_json, write_json

CHALLENGE = os.path.join("supervisor", "release_challenge.json")
LOCK = os.path.join("supervisor", "release.lock")  # opstate.lock과 따로: _clear가 opstate.lock을 다시 잡는다
TTL_S, MAX_TRIES = 600, 3
CONDITIONS = tuple(n for n in opstate.LEVEL if n != opstate.DONE)
TASK_KINDS = ("interrupts", "holder")
WORD, PREFIX = "재개", "[release-hook] "
NOTE = "확인 코드는 사용자 인증이 아니다(sandbox 밖 같은 macOS 사용자 프로세스와 구분하지 못한다)"


def evidence(root, target):
    """(풀 수 있는 대상이 지금 있는가, 사람에게 보일 근거 문장). 아무것도 쓰지 않는다."""
    kind, _, key = target.partition(":")
    if kind in TASK_KINDS:
        name = "stopped.json" if kind == "interrupts" else "lease.json"
        try:
            found = read_json(os.path.join(root, "tasks", ct.check_key(key), name))
        except (ct.ContractError, OSError, ValueError) as exc:
            return False, "해제하지 않음: %s를 읽지 못함(%s)." % (target, type(exc).__name__)
        if found is None:
            return False, "해제할 것 없음: %s에 %s가 없다." % (key, name)
        return True, "근거 %s (%s): %s" % (target, name, json.dumps(found, ensure_ascii=False, sort_keys=True))
    if target not in CONDITIONS:
        return False, "대상 아님: %r. 이름 하나만(%s, interrupts:<키>, holder:<키>). awaiting·blocked 작업은 상태 조회로 보고 수동 절차로 푼다." % (
            target, "·".join(CONDITIONS))
    try:
        state = opstate.load(root)
    except OSError as exc:
        return False, "해제하지 않음: 운영 상태를 읽지 못함(%s)." % type(exc).__name__
    if state.get("unreadable"):
        return False, "해제하지 않음: 운영 상태 파일 손상(덮어쓰지 않는다, 수동 복구). %s" % state["conditions"][opstate.INTEGRITY_HALT]["reason"]
    info = state["conditions"].get(target)
    if info is None:
        return False, "해제할 것 없음: %s 조건이 없다(현재 %s)." % (target, opstate.effective(state))
    group = "사용량 한도: 자동 재개 대상, 소진이면 사람만" if target in opstate.RATE_LIMITED else "사용자 해제 대상: 자동 해제 없음"
    shown = {k: info[k] for k in ("since", "actor", "reason", "next_try_at", "exhausted", "unknown_attempts") if k in info}
    return True, "근거 %s [%s]: %s" % (target, group, json.dumps(shown, ensure_ascii=False, sort_keys=True))


def request(root, target, now, source):
    """1단계. (종료 코드, 근거·안내 문장, 확인 코드 또는 None). 코드는 호출자가 사용자에게만 보이는 곳에 따로 낸다."""
    found, text = evidence(root, target)
    if not found:
        return 1, text + " 확인 코드를 만들지 않았다.", None
    code, salt = "%06d" % secrets.randbelow(10 ** 6), secrets.token_hex(16)
    path = os.path.join(root, CHALLENGE)
    try:
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        with open(os.path.join(root, LOCK), "a") as guard:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
            write_json(path, {"target": target, "salt": salt, "digest": hashlib.sha256((salt + code).encode()).hexdigest(),
                              "issued_at": now, "expires_at": now + TTL_S, "tries": 0, "source": source})
            try:
                ledger.append(os.path.join(root, "ledger.jsonl"), now, "release_challenge",
                              {"op": "issued", "target": target, "source": source, "expires_at": now + TTL_S})
            except Exception:
                os.unlink(path)  # 장부에 남지 않은 코드는 두지 않는다
                raise
    except Exception as exc:  # noqa: BLE001 — 어디서 막혔든 코드를 내주지 않는다
        return 1, "%s 확인 코드를 만들지 못함(%s): 중단 상태 유지." % (text, type(exc).__name__), None
    return 0, "%s 확인 코드를 발급했다(%d분, 1회, 대상 %s, 이전 코드는 무효). 풀려면 2단계에 이 코드를 넣는다. %s." % (
        text, TTL_S // 60, target, NOTE), code


def _take(root, target, code, now):
    """잠금 안에서 확인 코드를 대조해 맞으면 지운다(1회). 맞으면 None, 아니면 거절 사유(장부에 남긴다). 쓰지 못하면 OSError."""
    path = os.path.join(root, CHALLENGE)
    with open(os.path.join(root, LOCK), "a") as guard:  # sandbox 안에서는 여기서 쓰기 거절: 기록을 읽지도 지우지도 않는다
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        try:
            ask = read_json(path)
        except ValueError:
            ask = None
        fields = (("target", str), ("salt", str), ("digest", str), ("tries", int), ("expires_at", (int, float)))
        if not isinstance(ask, dict) or not all(isinstance(ask.get(k), t) and type(ask.get(k)) is not bool for k, t in fields):
            why, ask = "발급된 확인 코드가 없다(또는 기록 손상)", None
        elif ask["target"] != target:
            why = "다른 대상의 확인 코드"
        elif now > ask["expires_at"]:
            why = "만료된 확인 코드"
        elif hmac.compare_digest(ask["digest"], hashlib.sha256((ask["salt"] + code).encode()).hexdigest()):
            os.unlink(path)
            return None
        else:
            why = "코드 불일치"
        if ask is not None:
            ask["tries"] += 1
            if ask["tries"] >= MAX_TRIES or why == "만료된 확인 코드":
                os.unlink(path)
            else:
                write_json(path, ask)
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "release_challenge", {"op": "rejected", "target": target, "why": why})
    return why


def answer(root, target, code, reason, now, source, confirm=False):
    """2단계. (종료 코드, 문장). confirm·사유·확인 코드가 모두 맞을 때만 그 대상 하나를 푼다. 하나라도 어긋나면 그대로 둔다."""
    if confirm is not True or not isinstance(reason, str) or not reason.strip() or not isinstance(code, str):
        return 1, "해제 안 함: --confirm·사유·확인 코드가 모두 필요하다. 중단 상태 유지."
    try:
        why = _take(root, target, code, now)
    except Exception as exc:  # noqa: BLE001 — 대조를 끝내지 못하면 풀지 않는다
        return 1, "해제 안 함: 확인 코드를 대조하지 못함(%s). 중단 상태 유지." % type(exc).__name__
    if why:
        return 1, "해제 안 함: %s. 중단 상태 유지(%d번 틀리거나 만료되면 1단계부터 다시)." % (why, MAX_TRIES)
    said = "%s [경로=%s, 확인 코드 일치. %s]" % (reason.strip(), source, NOTE)
    kind, _, key = target.partition(":")
    if kind in TASK_KINDS:
        release = unlock.release_interrupts if kind == "interrupts" else unlock.release_holder
        try:
            got = release(root, key, "user", said, now, confirm=True)
        except Exception as exc:  # noqa: BLE001
            got = {"ok": False, "reason": type(exc).__name__}
        if not got["ok"]:
            return 1, "해제 안 함: %s (%s). 작업 정지 유지(코드는 썼다: 다시 하려면 1단계부터)." % (target, got["reason"])
        return 0, "해제 확인: %s (보관 %s). 다음 claim이 정상 규칙대로 다룬다." % (target, os.path.relpath(got["archived"], root))
    error = ""
    try:
        if not opstate.clear_by_user(root, target, now, said):
            error = " (이미 없던 조건)"
    except Exception as exc:  # noqa: BLE001 — 상태는 바꿨는데 장부만 실패할 수 있어 아래에서 다시 읽는다
        error = " (해제 중 오류: %s)" % type(exc).__name__
    try:
        state = opstate.load(root)
    except OSError as exc:
        return 1, "해제했는지 확인하지 못함%s: 상태 파일을 읽을 수 없음(%s). 풀렸다고 보지 말 것." % (error, type(exc).__name__)
    if state.get("unreadable") or target in state["conditions"]:
        return 1, "해제 안 됨%s: 현재 상태 %s." % (error, opstate.effective(state))
    text = "해제 확인: %s%s. 현재 상태 %s." % (target, error, opstate.effective(state))
    if target in opstate.RATE_LIMITED:
        try:
            seen = read_json(os.path.join(root, claude_job.UNKNOWN_LIMIT)) or {"attempts": 0}
            count = seen["attempts"]
        except (OSError, ValueError, KeyError, TypeError):
            count = "읽지 못함(Supervisor는 소진으로 본다)"
        text += " 시각 미상 한도 시도 횟수 %s/%d는 그대로 둔다(초기화는 사람이 %s를 지우는 별도 절차)." % (
            count, claude_job.MAX_UNKNOWN_RETRIES, claude_job.UNKNOWN_LIMIT)
    return 0, text


def from_prompt(data):
    """훅 표준입력 바이트 → None(재개 문구가 아님: 원래 훅이 처리) | (대상, 코드 또는 None). 대상이 ""이면 형식 안내만 한다."""
    try:
        payload = json.loads(data.decode("utf-8"))
        prompt = payload["prompt"] if payload["hook_event_name"] == "UserPromptSubmit" else None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if not isinstance(prompt, str):
        return None
    text = unicodedata.normalize("NFC", prompt.strip())
    if text != WORD and not text.startswith(WORD + " "):
        return None  # "재개해" 같은 대화 문장은 명령이 아니다
    parts = text.split(" ")
    if len(parts) == 2 and parts[1] or len(parts) == 3 and parts[1] and re.fullmatch(r"[0-9]{6}", parts[2]):
        return parts[1], parts[2] if len(parts) == 3 else None
    return "", None


def _args(argv):
    parser = argparse.ArgumentParser(prog="python -m harness.control_release", allow_abbrev=False,
                                     description="사람 해제: --code 없이 1단계(근거·확인 코드), --code·--reason·--confirm으로 2단계")
    parser.add_argument("--root", required=True, help="하네스 root 폴더")
    parser.add_argument("--target", required=True, help="조건 이름 하나 또는 interrupts:<키>·holder:<키>")
    parser.add_argument("--code")
    parser.add_argument("--reason", default="")
    parser.add_argument("--confirm", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    ARGS = _args(sys.argv[1:])
    ROOT = os.path.abspath(ARGS.root)
    if not status.is_harness_root(ROOT):
        print("하네스 root가 아니라 아무것도 하지 않음(supervisor·tasks·ledger.jsonl이 없음): %s" % ROOT)
        sys.exit(1)
    if ARGS.code is None:
        CODE, TEXT, SECRET = request(ROOT, ARGS.target, time.time(), "terminal")
        print(TEXT)
        if SECRET:
            print("확인 코드: %s" % SECRET, file=sys.stderr)
    else:
        CODE, TEXT = answer(ROOT, ARGS.target, ARGS.code, ARGS.reason, time.time(), "terminal", ARGS.confirm)
        print(TEXT)
    sys.exit(CODE)
