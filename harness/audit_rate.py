"""비동기 감사의 순수 계산: 감사 상태 접기, 감사율 일정, 표본 추출(audit.py의 함수 수 한도 때문에 분리). 파일·네트워크를 쓰지 않는다.

감사율 일정(설계 5-4, D-3): 새 정책의 처음 initial_rounds 회차(감사를 통과한 회차 수)는 초기 비율(제안 10%). 그 뒤 누적 감사 오류율이 정책 상한 이하이면
회차마다 절반으로 낮추되 floor(제안 최저 2%) 아래로 내리지 않는다. 누적 오류율이 상한을 넘으면 초기 비율로 되돌린다. 분포 변화·Champion–Silver 불일치
급증 신호가 오면 초기 비율로 올리고 연속 통과 회차를 0으로 되돌린다. 수동 조정(set_rate)은 다음 계획부터 그 값을 쓰고 신호가 오면 해제된다.
감사율 0(이하)은 어떤 경로로도 거절한다. 표본은 sha256(seed|라벨 ID) 순서의 앞 k개라서 같은 seed는 같은 표본이다(파이썬 난수 구현에 의존하지 않음).
"""
import hashlib
import math
from fractions import Fraction

from harness import silver_policy

SIGNAL_KEYS = ("distribution_shift", "champion_silver_disagreement")
# 제안값(실제 값은 호출자가 schedule로 사전 등록한다). 최저 2%는 D-3의 제안값이며 초기 회차 수는 설계에 값이 없어 임의의 시작 제안이다
SUGGESTED_SCHEDULE = {"initial": 0.10, "floor": 0.02, "initial_rounds": 3}
NEW_POLICY = {"rate": None, "override": None, "clean_rounds": 0, "audited": 0, "errors": 0}


class AuditError(Exception):
    pass


def check_plan_inputs(schedule, signals):
    """일정·신호를 검사해 (initial, floor, initial_rounds, 켜진 신호 목록)을 돌려준다. 0 < floor ≤ initial ≤ 1이 아니면 AuditError."""
    if not isinstance(schedule, dict) or set(schedule) != {"initial", "floor", "initial_rounds"}:
        raise AuditError("schedule은 initial·floor·initial_rounds를 가진 dict(사전 등록 값, 기본값 없음)")
    initial, floor = silver_policy.ratio(schedule["initial"]), silver_policy.ratio(schedule["floor"])
    rounds = schedule["initial_rounds"]
    if not 0 < floor <= initial <= 1 or not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
        raise AuditError("감사율은 0 < floor ≤ initial ≤ 1(0%는 금지), initial_rounds는 1 이상의 정수")
    signals = {} if signals is None else signals
    if not isinstance(signals, dict) or set(signals) - set(SIGNAL_KEYS) or any(not isinstance(v, bool) for v in signals.values()):
        raise AuditError("signals는 %s를 키로 갖는 bool dict" % (SIGNAL_KEYS,))
    return initial, floor, rounds, sorted(k for k, v in signals.items() if v)


def fold_audit(entries):
    """감사 상태 {batches: {id: {plan, not_required, verdicts, completed, cascade}}, policies: {id: {rate, override, clean_rounds, audited, errors}}}."""
    batches, policies = {}, {}
    for entry in entries:
        event, data = entry["event"], entry["data"]
        if event == "audit_rate_set":
            state = policies.setdefault(data["policy_id"], dict(NEW_POLICY))
            state.update(rate=Fraction(data["rate"]), override=Fraction(data["rate"]))
        if event not in ("audit_planned", "audit_not_required", "audit_verdicts", "audit_completed", "cascade_done"):
            continue
        batch = batches.setdefault(data["batch_id"], {"plan": None, "not_required": False, "verdicts": {}, "completed": None,
                                                      "cascade": None})
        if event == "audit_planned":
            batch["plan"] = data
            state = policies.setdefault(data["policy_id"], dict(NEW_POLICY))
            state["rate"] = Fraction(data["rate"])
            if data["raised"]:
                state.update(clean_rounds=0, override=None)
        elif event == "audit_not_required":
            batch["not_required"] = True
        elif event == "audit_verdicts":
            batch["verdicts"].update(data["verdicts"])
        elif event == "audit_completed":
            batch["completed"] = data
            state = policies.setdefault(data["policy_id"], dict(NEW_POLICY))
            state["audited"] += data["n_sample"]
            state["errors"] += data["errors"]
            state["clean_rounds"] += 1 if data["status"] == "complete" else 0
        else:
            batch["cascade"] = data
    return {"batches": batches, "policies": policies}


def rate_for(policy_state, active, initial, floor, rounds, cap):
    """다음 감사 계획의 (감사율, 근거 dict, 신호로 올렸는지)."""
    if active:
        return initial, {"why": "signal", "signals": active}, True
    if policy_state["override"] is not None:
        return policy_state["override"], {"why": "manual_override"}, False
    if policy_state["clean_rounds"] < rounds:
        return initial, {"why": "initial_rounds", "clean_rounds": policy_state["clean_rounds"], "of": rounds}, False
    audited, errors = policy_state["audited"], policy_state["errors"]
    if audited and Fraction(errors, audited) > cap:
        return initial, {"why": "cumulative_error_over_cap", "errors": errors, "audited": audited}, False
    prev = policy_state["rate"]
    lowered = prev / 2 if prev / 2 >= floor else min(prev, floor)
    return lowered, {"why": "decay", "errors": errors, "audited": audited, "clean_rounds": policy_state["clean_rounds"]}, False


def sample_ids(ids, rate, seed):
    """rate × len(ids)를 올림(최소 1)한 개수만큼 seed 고정 순서로 고른 라벨 ID(정렬). ids가 비면 빈 목록."""
    count = min(len(ids), max(1, math.ceil(rate * len(ids))))
    order = sorted((hashlib.sha256(("%s|%s" % (seed, i)).encode("utf-8")).hexdigest(), i) for i in ids)
    return sorted(i for _, i in order[:count])
