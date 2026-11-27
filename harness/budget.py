"""개발 예산(DECISIONS D-2, 2026-11-27 확정): 주당 실험 20건, 비전 호출 300구역, 봉인 교체 주기당 승격 2건.

- 사용량은 추가 전용 해시 체인 장부 root/supervisor/budget.jsonl(1단계 ledger)에 charge 이벤트로 남긴다. 덮어쓰지 않는다.
- 주 경계는 호출자가 준 시각(now)으로 정한다: UTC 기준 ISO 주(월요일 00:00 UTC = 한국 시각 월요일 09:00. 가정, 인계 참조).
  승격은 호출자가 준 봉인 교체 주기 ID(seal_cycle)로 센다.
- 한도를 넘는 charge는 기록하지 않고 BUDGET_EXCEEDED를 켜고 알림을 남긴다(중단·보고). 자동 재개 경로는 없다:
  BUDGET_EXCEEDED(및 다른 정지 상태)가 켜져 있는 동안 charge는 모두 거절되고, 해제는 opstate.clear_by_user(사람)뿐이다(예산 재승인 필요).
- 호출자: 실험을 시작하는 쪽(4단계 계획 관문)과 비전 작업(5단계)이 charge를 부른다. Supervisor 루프는 부르지 않는다.
- 장부가 손상됐으면 BudgetError(사용량을 추정하지 않는다).
호출 깊이: charge → usage → ledger.verify → _check_line → _hash_entry (4), charge → opstate.set_condition → ledger.append → _hash_entry (3).
"""
import datetime
import fcntl
import json
import os

from . import ledger, opstate

LIMITS = {"experiment": ("week", 20), "vision_zone": ("week", 300), "promotion": ("seal_cycle", 2)}
BUDGET = os.path.join("supervisor", "budget.jsonl")


class BudgetError(Exception):
    pass


def period_of(kind, now, seal_cycle=None):
    """사용량을 묶는 기간 키: "week:2026-W48" 또는 "seal:<주기 ID>"."""
    if kind not in LIMITS:
        raise BudgetError("알 수 없는 예산 항목: %r" % (kind,))
    if LIMITS[kind][0] == "seal_cycle":
        if not isinstance(seal_cycle, str) or not seal_cycle:
            raise BudgetError("승격 예산은 봉인 교체 주기 ID가 필요하다")
        return "seal:" + seal_cycle
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        raise BudgetError("now는 epoch 초 숫자여야 한다")
    year, week = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isocalendar()[:2]
    return "week:%04d-W%02d" % (year, week)


def usage(root, kind, period):
    """장부 체인을 검증한 뒤 (kind, period)의 사용량 합. 장부가 손상됐으면 BudgetError."""
    path = os.path.join(root, BUDGET)
    problems = ledger.verify(path)
    if problems:
        raise BudgetError("예산 장부 손상: %s" % problems[:3])
    total = 0
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                data = json.loads(raw)["data"]
                if data.get("kind") == kind and data.get("period") == period:
                    total += data["amount"]
    return total


def charge(root, kind, amount, now, seal_cycle=None, actor="harness"):
    """사용량 amount를 기록한다. {"ok", "kind", "period", "used", "limit"}. 넘으면 기록하지 않고 BUDGET_EXCEEDED(ok=False)."""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise BudgetError("amount는 양의 정수여야 한다")
    period, limit = period_of(kind, now, seal_cycle), LIMITS[kind][1]
    os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
    with open(os.path.join(root, "supervisor", "budget.lock"), "a") as guard:  # 확인과 기록 사이에 다른 charge가 끼지 않게
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        result = {"kind": kind, "period": period, "limit": limit, "requested": amount}
        halted = opstate.effective(opstate.load(root))
        if halted in opstate.HALTING:  # 예산 초과·무결성 정지·사용자 중단·종료 중에는 새 개발 작업을 허락하지 않는다
            return dict(result, ok=False, reason="halted:" + halted, used=None)
        used = usage(root, kind, period)
        if used + amount > limit:
            info = dict(result, used=used)
            opstate.set_condition(root, opstate.BUDGET_EXCEEDED, now, actor, "개발 예산 초과: %s" % kind, info)
            opstate.notify(root, now, "budget_exceeded", "개발 예산 초과(재승인 필요): %s %s" % (kind, period), info)
            return dict(info, ok=False, reason="limit")
        ledger.append(os.path.join(root, BUDGET), now, "charge",
                      {"kind": kind, "period": period, "amount": amount, "actor": actor})
        return dict(result, ok=True, used=used + amount)
