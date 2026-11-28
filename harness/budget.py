"""개발 예산(DECISIONS D-2, 2026-11-27 확정): 주당 실험 20건, 비전 호출 300구역, 봉인 교체 주기당 승격 2건.

- 사용량은 추가 전용 해시 체인 장부 root/supervisor/budget.jsonl(1단계 ledger)에 charge 이벤트로 남긴다. 덮어쓰지 않는다.
- 주 경계는 호출자가 준 시각(now)으로 정한다: UTC 기준 ISO 주(월요일 00:00 UTC = 한국 시각 월요일 09:00. 가정, 인계 참조).
  승격은 호출자가 준 봉인 교체 주기 ID(seal_cycle)로 센다.
- 한도를 넘는 charge는 기록하지 않고 BUDGET_EXCEEDED를 켜고 알림을 남긴다(중단·보고). 자동 재개 경로는 없다:
  BUDGET_EXCEEDED(및 다른 정지 상태)가 켜져 있는 동안 charge는 모두 거절되고, 해제는 opstate.clear_by_user(사람)뿐이다(예산 재승인 필요).
- 호출자: 실험을 시작하는 쪽(runner.drain: 실험·학습·평가 executor 직전, key = 논리 실험 키)과 비전 작업(5단계)이 charge를 부른다. Supervisor 루프는 부르지 않는다.
- 취소(B5-4, 사용자 결정 3 "실행되지 않았음이 객관적으로 확인된 경우에만 취소"): cancel 이벤트 하나만 더했다. cancel은 charge가 돌려준 차감 번호(seq)
  하나를 한 번만 되돌리며 그 차감의 기간(주)에서 뺀다(다음 주 예산을 비우지 않는다). 취소된 차감은 key 멱등의 근거가 아니다(다시 시작하면 새로 차감).
  앞선 같은 (kind, key, period, amount) 차감을 가리키지 않거나 같은 차감을 두 번 되돌리는 cancel 줄·모르는 이벤트는 위조·손상으로 BudgetError
  (사용량을 추정하지 않고 모든 차감을 거절한다). 무엇이 '실행되지 않음'인지는 호출자(runner, 어댑터 not_started)가 정한다.
- 장부가 손상됐으면 BudgetError(사용량을 추정하지 않는다). 꼬리 잘림(마지막 줄 삭제)은 체인만으로는 보이지 않으므로 charge마다 마지막
  해시를 root/supervisor/budget.tail.json에 남기고 usage가 ledger.verify(expected_tail)로 대조한다. 장부에 한 줄 쓰고 꼬리를 쓰기 전에
  죽은 경우(마지막 줄의 prev가 저장한 꼬리)만 정상으로 인정한다. 꼬리 파일이 없으면 GENESIS로 본다(줄이 있으면 거절).
  한계: 장부와 꼬리 파일을 함께 지우거나 함께 고치면 알 수 없다(같은 root 안의 복제본이다. 외부 복제는 DESIGN 9절 cardeval 몫).
- now는 유한한 epoch 초 숫자만 받는다(NaN·무한대·bool·문자열은 BudgetError).
호출 깊이(B5-3, 동작 불변으로 펼침): charge는 최대 2회 전이다(charge → ledger.verify → _check_line, charge → opstate.load → read_json,
charge → opstate.notify → ledger.append). 호출 지점 runner.main → drain → charge와 supervisor.run → claude_job.execute → charge가 4를 넘지 않게
usage(→ ledger.verify)를 거치지 않고 같은 검증을 _tally로 나눴고, BUDGET_EXCEEDED 전이는 opstate.set_condition과 같은 단계(opstate.lock 안에서
load → 상태 파일 원자 저장 → root/ledger.jsonl opstate_transition 한 줄)를 여기에 펼쳤다. 어긋나면 tests/test_harness_b5_budget_depth.py의
set_condition 동치 시험이 잡는다. opstate 쪽 전이 규칙을 바꾸면 이 펼친 부분도 같이 바꾼다.
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


def _tally(problems, rows, tail, kind, period):
    """검증 결과(problems)·장부 줄·저장한 꼬리로 ((kind, period) 사용량 합, 취소된 차감 번호 집합). 손상·잘림·맞지 않는 취소는 BudgetError.
    다른 함수를 부르지 않는다."""
    if any(p["problem"] != "tail_mismatch" for p in problems):
        raise BudgetError("예산 장부 손상: %s" % problems[:3])
    if problems and not (rows and rows[-1]["prev"] == tail):  # 꼬리 기록 전에 죽은 한 줄만 허용한다
        raise BudgetError("예산 장부 꼬리 불일치(잘림·삭제 의심): %s" % problems)
    charges, cancelled = {}, set()
    for row in rows:
        data = row["data"] if isinstance(row["data"], dict) else None
        if data is not None and row["event"] == "charge":
            charges[row["seq"]] = data
            continue
        ref = data.get("charge_seq") if data is not None else None
        base = charges.get(ref) if type(ref) is int else None  # 앞선 줄의 차감만(bool·문자열 번호 거절)
        if data is None or row["event"] != "cancel" or base is None or ref in cancelled or not isinstance(base.get("key"), str) \
                or any(base.get(f) != data.get(f) for f in ("kind", "key", "period", "amount")):
            raise BudgetError("예산 장부의 취소·이벤트 기록이 앞선 차감과 맞지 않는다(위조·중복 의심): seq %r" % row["seq"])
        cancelled.add(ref)
    return sum(d["amount"] for s, d in charges.items() if s not in cancelled and d.get("kind") == kind and d.get("period") == period), cancelled


def usage(root, kind, period):
    """장부 체인과 저장한 꼬리를 검증한 뒤 (kind, period)의 사용량 합. 장부가 손상·잘렸으면 BudgetError."""
    path = os.path.join(root, BUDGET)
    try:
        tail = read_json(os.path.join(root, TAIL), {}).get("hash", ledger.GENESIS)
    except (ValueError, AttributeError) as exc:
        raise BudgetError("예산 꼬리 기록 손상: %s" % exc)
    problems = ledger.verify(path, expected_tail=tail)
    rows = []
    if not any(p["problem"] != "tail_mismatch" for p in problems) and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            rows = [json.loads(raw) for raw in handle]
    return _tally(problems, rows, tail, kind, period)[0]


def charge(root, kind, amount, now, seal_cycle=None, actor="harness", key=None):
    """사용량 amount를 기록한다. {"ok", "kind", "period", "used", "limit"}. 넘으면 기록하지 않고 BUDGET_EXCEEDED(ok=False).

    key(멱등 키, 작업 계약 2단계): 같은 종류(kind)·같은 key의 charge가 이미 장부에 있으면 다시 차감하지 않고 ok=True·already=True를 돌려준다(같은 단계의
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
        path = os.path.join(root, BUDGET)  # usage와 같은 검증(깊이를 줄이려고 usage를 거치지 않는다. 손상이면 BudgetError)
        try:
            tail = read_json(os.path.join(root, TAIL), {}).get("hash", ledger.GENESIS)
        except (ValueError, AttributeError) as exc:
            raise BudgetError("예산 꼬리 기록 손상: %s" % exc)
        problems = ledger.verify(path, expected_tail=tail)
        rows = []
        if not any(p["problem"] != "tail_mismatch" for p in problems) and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                rows = [json.loads(raw) for raw in handle]
        used, cancelled = _tally(problems, rows, tail, kind, period)
        if problems:  # 꼬리 기록 전에 죽은 한 줄(_tally가 인정): 꼬리를 먼저 맞춘다(그 줄을 지워 사용량을 되돌리지 못하게, 다음 kill이 두 줄 차이가 되지 않게)
            write_json(os.path.join(root, TAIL), {"hash": rows[-1]["hash"], "seq": rows[-1]["seq"]})
        if key is not None and any(row["event"] == "charge" and row["seq"] not in cancelled
                                   and (row["data"].get("kind"), row["data"].get("key")) == (kind, key) for row in rows):
            return dict(result, ok=True, already=True, used=used)
        if used + amount > limit:
            info = dict(result, used=used)
            reason = "개발 예산 초과: %s" % kind
            with open(os.path.join(root, opstate.LOCK), "a") as op_guard:  # opstate.set_condition과 같은 전이(펼침, 모듈 설명 참조)
                fcntl.flock(op_guard.fileno(), fcntl.LOCK_EX)
                state = opstate.load(root)
                if state.get("unreadable") or not actor:
                    raise opstate.OpStateError("운영 상태 파일이 손상되어 덮어쓰지 않거나 실행자가 없다")
                before = opstate.effective(state)
                state["conditions"][opstate.BUDGET_EXCEEDED] = dict(info, since=now, actor=actor, reason=reason)
                write_json(os.path.join(root, opstate.OPSTATE), state)
                ledger.append(os.path.join(root, "ledger.jsonl"), now, "opstate_transition", {
                    "op": "set", "condition": opstate.BUDGET_EXCEEDED, "effective_before": before,
                    "effective_after": opstate.effective(state), "actor": actor, "reason": reason, "extra": info})
            opstate.notify(root, now, "budget_exceeded", "개발 예산 초과(재승인 필요): %s %s" % (kind, period), info)
            return dict(info, ok=False, reason="limit")
        entry = ledger.append(os.path.join(root, BUDGET), now, "charge", dict(
            {"kind": kind, "period": period, "amount": amount, "actor": actor}, **({"key": key} if key is not None else {})))
        write_json(os.path.join(root, TAIL), {"hash": entry["hash"], "seq": entry["seq"]})
        return dict(result, ok=True, used=used + amount, seq=entry["seq"])


def cancel(root, kind, key, seq, now, actor="harness", reason="not_started"):
    """charge가 돌려준 차감 하나(seq)를 되돌린다(cancel 이벤트, 모듈 설명 참조). {"ok", "kind", "period"(그 차감의 기간), "used"(그 기간의 취소 뒤 사용량)}.
    이미 취소된 차감이면 ok·already(kill 뒤 다시 부른 취소, 두 번 빼지 않는다). 그 번호가 같은 kind·key의 차감이 아니면 기록하지 않고 ok=False.
    정지 상태는 보지 않는다(취소는 작업을 시작하지 않는다). 장부 손상·맞지 않는 취소 줄은 BudgetError. 호출 깊이 2(charge와 같은 검증을 펼쳤다)."""
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise BudgetError("now는 유한한 epoch 초 숫자여야 한다")
    if kind not in LIMITS or not isinstance(key, str) or not key or type(seq) is not int:
        return {"ok": False, "reason": "bad_request", "kind": kind}
    os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
    with open(os.path.join(root, "supervisor", "budget.lock"), "a") as guard:  # charge와 같은 잠금: 확인과 기록 사이에 다른 charge·cancel이 끼지 않게
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        path = os.path.join(root, BUDGET)
        try:
            tail = read_json(os.path.join(root, TAIL), {}).get("hash", ledger.GENESIS)
        except (ValueError, AttributeError) as exc:
            raise BudgetError("예산 꼬리 기록 손상: %s" % exc)
        problems = ledger.verify(path, expected_tail=tail)
        rows = []
        if not any(p["problem"] != "tail_mismatch" for p in problems) and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                rows = [json.loads(raw) for raw in handle]
        base = next((r["data"] for r in rows if r["seq"] == seq and r["event"] == "charge"), None)
        used, cancelled = _tally(problems, rows, tail, kind, base.get("period") if base else None)
        if problems:  # charge와 같은 꼬리 맞춤
            write_json(os.path.join(root, TAIL), {"hash": rows[-1]["hash"], "seq": rows[-1]["seq"]})
        if base is None or (base.get("kind"), base.get("key")) != (kind, key):
            return {"ok": False, "reason": "no_matching_charge", "kind": kind}
        result = {"ok": True, "kind": kind, "period": base["period"]}
        if seq in cancelled:
            return dict(result, already=True, used=used)
        entry = ledger.append(path, now, "cancel", {"kind": kind, "key": key, "charge_seq": seq, "period": base["period"],
                                                    "amount": base["amount"], "actor": actor, "reason": reason})
        write_json(os.path.join(root, TAIL), {"hash": entry["hash"], "seq": entry["seq"]})
        return dict(result, used=used - base["amount"])
