"""운영 상태(DESIGN 12절). root/supervisor/opstate.json에 "조건" 목록을 두고, 유효 상태는 우선순위가 가장 높은 조건이다.

우선순위: INTEGRITY_HALT > USER_STOPPED > DONE > BUDGET_EXCEEDED > RATE_LIMITED_SHORT / RATE_LIMITED_WEEKLY /
RATE_LIMITED_UNKNOWN(같은 단계, 한 번에 하나만 둔다) > RUNNING(조건 없음).
- RATE_LIMITED_UNKNOWN: 한도 이벤트에서 단기/주간을 구분할 수 없을 때. 단기로 추정하지 않는다(배정 명세 B).
- 위의 네 정지 상태는 자동 해제 금지: 해제는 clear_by_user(actor="user")뿐이며 Supervisor 루프는 이 함수를 부르지 않는다.
  clear_auto는 한도 조건만, 그리고 3회 소진(exhausted)이 아닌 것만 푼다.
- 저장은 jsonio.write_json(임시 파일+fsync+os.replace). 전이마다 상태 파일을 먼저 바꾸고 1단계 장부(root/ledger.jsonl)에 남긴다
  (1단계 규칙: 기록은 상태 변경 뒤). 장부가 손상돼 INTEGRITY_HALT 기록을 못 쓰면 상태 파일에 ledger_error로 남긴다.
- 상태 파일이 깨졌으면 덮어쓰지 않고(증거 보존) 읽는 쪽에는 INTEGRITY_HALT로 보인다(fail-closed).
호출 깊이: 공개 함수는 load·effective·write_json·ledger.append(→_hash_entry)만 부른다(최대 2, clear_*는 _clear를 거쳐 3).
"""
import os

from . import ledger
from .jsonio import read_json, write_json

INTEGRITY_HALT, USER_STOPPED, DONE, BUDGET_EXCEEDED = "INTEGRITY_HALT", "USER_STOPPED", "DONE", "BUDGET_EXCEEDED"
RATE_LIMITED_SHORT, RATE_LIMITED_WEEKLY, RATE_LIMITED_UNKNOWN = \
    "RATE_LIMITED_SHORT", "RATE_LIMITED_WEEKLY", "RATE_LIMITED_UNKNOWN"
RUNNING = "RUNNING"
HALTING = (INTEGRITY_HALT, USER_STOPPED, DONE, BUDGET_EXCEEDED)  # 자동 해제 금지, 개발 작업 시작 안 함
RATE_LIMITED = (RATE_LIMITED_SHORT, RATE_LIMITED_WEEKLY, RATE_LIMITED_UNKNOWN)  # Claude 작업만 멈춤
LEVEL = {INTEGRITY_HALT: 0, USER_STOPPED: 1, DONE: 2, BUDGET_EXCEEDED: 3,
         RATE_LIMITED_SHORT: 4, RATE_LIMITED_WEEKLY: 4, RATE_LIMITED_UNKNOWN: 4}
OPSTATE = os.path.join("supervisor", "opstate.json")
NOTIFICATIONS = os.path.join("supervisor", "notifications.jsonl")


class OpStateError(Exception):
    pass


def load(root):
    """{"conditions": {상태: 정보}}. 파일이 없으면 조건 없음. 깨졌으면 INTEGRITY_HALT 하나만 있는 것처럼 보인다(unreadable=True)."""
    try:
        state = read_json(os.path.join(root, OPSTATE), {"conditions": {}})
        if not isinstance(state, dict) or not isinstance(state.get("conditions"), dict) \
                or not set(state["conditions"]) <= set(LEVEL):
            raise ValueError("형식 오류")
    except ValueError as exc:
        return {"conditions": {INTEGRITY_HALT: {"reason": "opstate_unreadable: %s" % exc}}, "unreadable": True}
    return state


def effective(state):
    """조건 중 우선순위가 가장 높은 상태. 조건이 없으면 RUNNING. 아무것도 부르지 않는다."""
    names = sorted(state["conditions"], key=LEVEL.__getitem__)
    return names[0] if names else RUNNING


def set_condition(root, name, now, actor, reason, extra=None):
    """조건을 켠다(같은 조건이면 정보 갱신). 한도 조건은 하나만 두므로 다른 한도 조건은 지운다. 기록한 조건 정보를 돌려준다."""
    if name not in LEVEL or not actor or not reason:
        raise OpStateError("알 수 없는 조건이거나 실행자·사유가 없다: %r" % (name,))
    state = load(root)
    if state.get("unreadable"):
        raise OpStateError("운영 상태 파일이 손상되어 덮어쓰지 않는다")
    before = effective(state)
    if name in RATE_LIMITED:
        for other in RATE_LIMITED:
            state["conditions"].pop(other, None)
    info = dict(extra or {}, since=now, actor=actor, reason=reason)
    state["conditions"][name] = info
    write_json(os.path.join(root, OPSTATE), state)
    data = {"op": "set", "condition": name, "effective_before": before, "effective_after": effective(state),
            "actor": actor, "reason": reason, "extra": extra or {}}
    try:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "opstate_transition", data)
    except ledger.LedgerError as exc:
        if name != INTEGRITY_HALT:
            raise
        info["ledger_error"] = str(exc)  # 장부를 못 쓰는 무결성 정지: 상태 파일이 정본이다
        write_json(os.path.join(root, OPSTATE), state)
    return info


def _clear(root, name, now, actor, reason):
    state = load(root)
    if state.get("unreadable"):
        raise OpStateError("운영 상태 파일이 손상되어 해제하지 않는다")
    if name not in state["conditions"]:
        return False
    before = effective(state)
    removed = state["conditions"].pop(name)
    write_json(os.path.join(root, OPSTATE), state)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, "opstate_transition",
                  {"op": "clear", "condition": name, "effective_before": before, "effective_after": effective(state),
                   "actor": actor, "reason": reason, "removed": removed})
    return True


def clear_auto(root, name, now, reason):
    """Supervisor용: 한도 조건만, 3회 소진이 아닌 것만 푼다. 그 밖은 OpStateError(자동 해제 금지)."""
    info = load(root)["conditions"].get(name)
    if name not in RATE_LIMITED or (isinstance(info, dict) and info.get("exhausted")):
        raise OpStateError("자동 해제 금지: %s" % name)
    return _clear(root, name, now, "supervisor", reason)


def clear_by_user(root, name, now, reason, actor="user"):
    """사람 확인 뒤 사용자가 부르는 해제 함수(Supervisor 루프에 호출 경로 없음). 해제했으면 True."""
    if actor != "user" or not reason:
        raise OpStateError("사용자만(actor='user') 사유와 함께 해제한다")
    return _clear(root, name, now, actor, reason)


def notify(root, now, kind, message, data=None):
    """알림 기록(추가 전용 해시 체인 notifications.jsonl). 실제 푸시·네트워크는 하지 않는다."""
    return ledger.append(os.path.join(root, NOTIFICATIONS), now, "notification",
                         {"kind": kind, "message": message, "data": data or {}})
