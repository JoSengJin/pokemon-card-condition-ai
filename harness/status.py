"""하네스 상태 수집(B6-1, 읽기 전용). collect(root, now)가 dict 하나를 돌려준다. 어떤 파일도 만들거나 고치지 않는다.

- 운영 상태가 깨졌거나 읽을 수 없으면 정상(RUNNING)으로 보지 않고 INTEGRITY_HALT·unreadable로 보인다(opstate.load와 같은 방향).
- 예산·장부·알림 장부의 손상은 그 항목의 오류·문제 수로 남기고 나머지 요약은 계속 만든다.
- 예산 읽기(budget.usage)는 budget.lock을 잡지 않는다. 한계: charge가 쓰는 순간에 조회하면 그 조회만 손상으로 보일 수 있다(다시 조회).
- Supervisor 실행 여부는 잠금 probe뿐이다(pid·시작 시각은 모른다, pre-b6 결정 6 현 설계 기본값).
- 승격 예산은 봉인 교체 주기 ID가 입력으로 필요해 요약에 넣지 않는다.
호출 깊이: collect → status_tasks.scan → states.facts → 말단 3, collect → budget.usage → ledger.verify → _check_line 3.
"""
import errno
import fcntl
import json
import os

from . import budget, ledger, opstate, status_tasks

NOTIFICATIONS_SHOWN = 3


def is_harness_root(root):
    """하네스가 쓴 흔적이 있는 폴더인가. 경로를 잘못 넣어 빈 폴더를 정상(RUNNING)으로 보거나 거기에 중단을 기록하지 않게."""
    return any(os.path.exists(os.path.join(root, name)) for name in ("supervisor", "tasks", "ledger.jsonl"))


def supervisor_running(root):
    """True(누가 Supervisor 잠금을 쥠) | False | None(확인 불가). 잠금 파일을 만들지 않고, 공유 잠금으로 확인한 뒤 곧바로 푼다
    (공유라서 조회 둘이 서로를 Supervisor로 보지 않는다). 한계: 확인하는 순간에 Supervisor가 시작하면 그 시작 한 번이 already_running이 된다."""
    try:
        fd = os.open(os.path.join(root, "supervisor", "supervisor.lock"), os.O_RDONLY)
    except FileNotFoundError:
        return False
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError as exc:
        return True if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES) else None
    finally:
        os.close(fd)  # 잠금을 잡았으면 닫으면서 풀린다
    return False


def collect(root, now):
    """운영 상태·Supervisor 잠금·작업·Claude 작업 칸·한도 횟수·예산(이번 주)·장부 검증·최근 알림."""
    try:
        state = opstate.load(root)
    except OSError as exc:
        state = {"conditions": {opstate.INTEGRITY_HALT: {"reason": "opstate_unreadable: %s" % exc}}, "unreadable": True}
    used = {}
    for kind in ("experiment", "vision_zone"):
        try:
            period = budget.period_of(kind, now)
            used[kind] = {"period": period, "limit": budget.LIMITS[kind][1], "used": budget.usage(root, kind, period)}
        except Exception as exc:  # noqa: BLE001 — 사용량을 추정하지 않고 오류로 보인다
            used[kind] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    problems = {}
    for name, rel in (("ledger", "ledger.jsonl"), ("notifications", opstate.NOTIFICATIONS)):
        try:
            problems[name] = len(ledger.verify(os.path.join(root, rel)))
        except (OSError, ValueError) as exc:
            problems[name] = "%s: %s" % (type(exc).__name__, exc)
    try:
        with open(os.path.join(root, opstate.NOTIFICATIONS), "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().removesuffix("\n").split("\n")
    except OSError:
        lines = []
    recent = []
    for raw in lines[-NOTIFICATIONS_SHOWN:]:
        try:
            row = json.loads(raw)
            recent.append({"ts": row["ts"], "kind": row["data"]["kind"], "message": row["data"]["message"]})
        except (ValueError, KeyError, TypeError):
            continue  # 손상은 위의 장부 문제 수로 보인다
    return dict(status_tasks.scan(root), now=now, state=opstate.effective(state), conditions=state["conditions"],
                unreadable=bool(state.get("unreadable")), supervisor_running=supervisor_running(root), budget=used,
                ledgers=problems, notifications=recent)
