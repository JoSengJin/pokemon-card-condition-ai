"""개발 예산(DECISIONS D-2, 2026-11-27 확정): 주당 실험 20건, 비전 호출 300구역, 봉인 교체 주기당 승격 2건.

- 사용량은 추가 전용 해시 체인 장부 root/supervisor/budget.jsonl(1단계 ledger)에 charge 이벤트로 남긴다. 덮어쓰지 않는다.
- 주 경계는 호출자가 준 시각(now)으로 정한다: UTC 기준 ISO 주(월요일 00:00 UTC = 한국 시각 월요일 09:00. 가정, 인계 참조).
  승격은 호출자가 준 봉인 교체 주기 ID(seal_cycle)로 센다.
- 한도를 넘는 charge는 기록하지 않고 BUDGET_EXCEEDED를 켜고 알림을 남긴다(중단·보고). 자동 재개 경로는 없다:
  BUDGET_EXCEEDED(및 다른 정지 상태)가 켜져 있는 동안 charge는 모두 거절되고, 해제는 opstate.clear_by_user(사람)뿐이다(예산 재승인 필요).
- 호출자: 실험을 시작하는 쪽(4단계 계획 관문)과 비전 작업(5단계)이 charge를 부른다. Supervisor 루프는 부르지 않는다.
- 장부가 손상됐으면 BudgetError(사용량을 추정하지 않는다). 꼬리 잘림(마지막 줄 삭제)은 체인만으로는 보이지 않으므로 charge마다 마지막
  해시를 root/supervisor/budget.tail.json에 남기고 usage가 ledger.verify(expected_tail)로 대조한다. 장부에 한 줄 쓰고 꼬리를 쓰기 전에
  죽은 경우(마지막 줄의 prev가 저장한 꼬리)만 정상으로 인정한다. 꼬리 파일이 없으면 GENESIS로 본다(줄이 있으면 거절).
  한계: 장부와 꼬리 파일을 함께 지우거나 함께 고치면 알 수 없다(같은 root 안의 복제본이다. 외부 복제는 DESIGN 9절 cardeval 몫).
- now는 유한한 epoch 초 숫자만 받는다(NaN·무한대·bool·문자열은 BudgetError).
호출 깊이: charge → usage → ledger.verify → _check_line (3), charge → opstate.set_condition → opstate.load → read_json (3).
"""
import datetime
import fcntl
import json
import math
import os

from . import ledger, opstate
from .jsonio import read_json, write_json

LIMITS = {"experiment": ("week", 20), "vision_zone": ("week", 300), "promotion": ("seal_cycle", 2)}
BUDGET = os.path.join("supervisor", "budget.jsonl")
TAIL = os.path.join("supervisor", "budget.tail.json")  # 마지막 해시(꼬리 잘림 확인용)


class BudgetError(Exception):
    pass


def period_of(kind, now, seal_cycle=None):
    """사용량을 묶는 기간 키: "week:2026-W48" 또는 "seal:<주기 ID>"."""
    if kind not in LIMITS:
        raise BudgetError("알 수 없는 예산 항목: %r" % (kind,))
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise BudgetError("now는 유한한 epoch 초 숫자여야 한다")
    if LIMITS[kind][0] == "seal_cycle":
        if not isinstance(seal_cycle, str) or not seal_cycle:
            raise BudgetError("승격 예산은 봉인 교체 주기 ID가 필요하다")
        return "seal:" + seal_cycle
    year, week = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isocalendar()[:2]
    return "week:%04d-W%02d" % (year, week)


def usage(root, kind, period):
    """장부 체인과 저장한 꼬리를 검증한 뒤 (kind, period)의 사용량 합. 장부가 손상·잘렸으면 BudgetError."""
    path = os.path.join(root, BUDGET)
    try:
        tail = read_json(os.path.join(root, TAIL), {}).get("hash", ledger.GENESIS)
    except (ValueError, AttributeError) as exc:
        raise BudgetError("예산 꼬리 기록 손상: %s" % exc)
    problems = ledger.verify(path, expected_tail=tail)
    if any(p["problem"] != "tail_mismatch" for p in problems):
        raise BudgetError("예산 장부 손상: %s" % problems[:3])
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            rows = [json.loads(raw) for raw in handle]
    if problems and not (rows and rows[-1]["prev"] == tail):  # 꼬리 기록 전에 죽은 한 줄만 허용한다
        raise BudgetError("예산 장부 꼬리 불일치(잘림·삭제 의심): %s" % problems)
    return sum(r["data"]["amount"] for r in rows if r["data"].get("kind") == kind and r["data"].get("period") == period)


def charge(root, kind, amount, now, seal_cycle=None, actor="harness", key=None):
    """사용량 amount를 기록한다. {"ok", "kind", "period", "used", "limit"}. 넘으면 기록하지 않고 BUDGET_EXCEEDED(ok=False).

    key(멱등 키, 작업 계약 2단계): 같은 key의 charge가 이미 장부에 있으면 다시 차감하지 않고 ok=True·already=True를 돌려준다(같은 단계의
    반영·복구에서 두 번 차감 방지). 언어 모델 재개처럼 실제 사용이 더 생기는 경우는 호출 시도마다 다른 key(예: task_key:run_token)를
    써서 승인 예산 안에서 차감한다. 호출부 연결은 5단계다."""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise BudgetError("amount는 양의 정수여야 한다")
    if key is not None and (not isinstance(key, str) or not key):
        raise BudgetError("key는 빈 문자열이 아닌 문자열이어야 한다")
    period, limit = period_of(kind, now, seal_cycle), LIMITS[kind][1]
    os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
    with open(os.path.join(root, "supervisor", "budget.lock"), "a") as guard:  # 확인과 기록 사이에 다른 charge가 끼지 않게
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        result = {"kind": kind, "period": period, "limit": limit, "requested": amount}
        halted = opstate.effective(opstate.load(root))
        if halted in opstate.HALTING:  # 예산 초과·무결성 정지·사용자 중단·종료 중에는 새 개발 작업을 허락하지 않는다
            return dict(result, ok=False, reason="halted:" + halted, used=None)
        used = usage(root, kind, period)  # 장부 검증도 여기서 한다(손상이면 BudgetError)
        if key is not None and os.path.exists(os.path.join(root, BUDGET)):
            with open(os.path.join(root, BUDGET), "r", encoding="utf-8") as handle:
                if any(json.loads(raw)["data"].get("key") == key for raw in handle):
                    return dict(result, ok=True, already=True, used=used)
        if used + amount > limit:
            info = dict(result, used=used)
            opstate.set_condition(root, opstate.BUDGET_EXCEEDED, now, actor, "개발 예산 초과: %s" % kind, info)
            opstate.notify(root, now, "budget_exceeded", "개발 예산 초과(재승인 필요): %s %s" % (kind, period), info)
            return dict(info, ok=False, reason="limit")
        entry = ledger.append(os.path.join(root, BUDGET), now, "charge", dict(
            {"kind": kind, "period": period, "amount": amount, "actor": actor}, **({"key": key} if key is not None else {})))
        write_json(os.path.join(root, TAIL), {"hash": entry["hash"], "seq": entry["seq"]})
        return dict(result, ok=True, used=used + amount)
