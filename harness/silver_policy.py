"""Silver 정책: 범위 `(결함 유형, 층, 라벨 값)` 승인, 정책 상태 접기, 보정 확인용 묶음 사용 횟수, 등급 전이 규칙, 미리 채운 입력 거절.

승인 조건(D-3, 설계 5-3): 보정 확인용 묶음에서 에이전트 제안과 사람 Gold를 대조한 오류율 ≤ 상한(10%). 오류율은 정확한 분수로 비교한다
(경계: 정확히 10%는 승인, 그보다 크면 거절). 조정용 묶음으로는 승인할 수 없고, 확인용 묶음을 평가에 쓸 때마다 사용을 장부에 남긴다(보정 과적합 감시).
승인된 범위 안에서는 라벨마다 승인을 받지 않는다. 철회된 정책은 되살리지 않고 같은 범위의 재승인은 새 판본(v2…)이다.
철회 쓰기는 수동·자동 모두 `withdrawal.withdraw` 하나로만 한다(이 파일에는 철회 쓰기가 없다). fold는 철회 기록과 감사 실패 기록을 모두 철회로 접는다.
이 파일의 쓰기 함수는 silver_store.lock 안에서 load → 판단 → append 순서이며, 다른 공개 함수를 부르지 않는다(호출 깊이).
"""
import hashlib
import math
from fractions import Fraction

from harness import silver_store

ERROR_CAP = Fraction(1, 10)  # D-3: Silver 정책 오류율 상한. 호출자는 이보다 느슨하게 설정할 수 없다
SCOPE_KEYS = ("defect_type", "stratum", "label_value")
LABEL_VALUES = ("defect", "normal")
# 예측·후보를 미리 채운 라벨 화면 입력에 쓰이는 필드 이름(앵커링 금지, 미리 채운 90구역 중 변경 0의 실측)
PREFILL_KEYS = frozenset(("prediction", "predictions", "predicted", "predicted_label", "prefill", "prefilled", "preselected",
                          "default_value", "model_label", "model_output", "model_score", "suggestion", "candidate_label",
                          "hint", "expected_label"))
_ALLOWED = frozenset(((None, "Silver"), (None, "Pending"), (None, "Gold"), ("Pending", "Silver"), ("Silver", "Pending")))


class PolicyError(Exception):
    pass


def ratio(value):
    """수 → 정확한 분수. bool·NaN·무한대·수가 아닌 값은 PolicyError."""
    ok = isinstance(value, (int, float, Fraction)) and not isinstance(value, bool)
    if not ok or (isinstance(value, float) and not math.isfinite(value)):
        raise PolicyError("비율은 유한한 수여야 한다: %r" % (value,))
    return Fraction(str(value))


def fold(entries):
    """장부 줄에서 정책 상태 {policies: {id: 정책+status}, uses: {보정 묶음 ID: 사용 횟수}}를 만든다. 앞뒤가 안 맞는 줄은 PolicyError."""
    policies, uses = {}, {}
    for entry in entries:
        event, data = entry["event"], entry["data"]
        if event == "policy_approved":
            policies[data["policy_id"]] = dict(data, status="approved")
        elif event == "policy_withdrawn":
            if data["policy_id"] not in policies:
                raise PolicyError("승인 기록 없는 정책의 철회: %s" % data["policy_id"])
            policies[data["policy_id"]].update(status="withdrawn", withdraw_reason=data["reason"])
        elif event == "audit_completed" and data["status"] == "failed" and policies.get(data["policy_id"], {}).get("status") == "approved":
            # 감사 실패 줄만 있고 철회 줄을 쓰기 전에 죽어도 그 정책은 철회된 것으로 접는다(신규 Silver·학습 사용·승격을 같은 순간부터 막는다)
            policies[data["policy_id"]].update(status="withdrawn", withdraw_reason="audit_failed")
        elif event == "calibration_used":
            uses[data["batch_id"]] = uses.get(data["batch_id"], 0) + 1
    return {"policies": policies, "uses": uses}


def active_policy(state, scope):
    """같은 (결함 유형, 층, 라벨 값) 범위의 승인된 정책, 없으면 None."""
    key = tuple(scope[k] for k in SCOPE_KEYS)
    for policy in state["policies"].values():
        if policy["status"] == "approved" and tuple(policy["scope"][k] for k in SCOPE_KEYS) == key:
            return policy
    return None


def approve(root, now, scope, confirm, *, cap, min_n):
    """보정 확인용 묶음 결과로 정책을 승인한다. 거절은 {"ok": False, "reason"}, 승인은 {"ok": True, "policy_id", ...}.

    confirm = {"batch_id", "role": "confirm"|"tune", "n": 대조한 구역 수, "errors": 사람 Gold와 다른 수}. min_n은 사전 등록 값(기본값 없음).
    cap은 ERROR_CAP 이하여야 한다(넘으면 PolicyError). 확인용 묶음은 평가에 쓰는 순간 사용 1회로 기록한다(거절돼도 기록).
    """
    if not isinstance(scope, dict) or any(not isinstance(scope.get(k), str) or not scope[k] for k in SCOPE_KEYS):
        raise PolicyError("scope는 %s가 모두 비어 있지 않은 문자열이어야 한다" % (SCOPE_KEYS,))
    scope = {k: scope[k] for k in SCOPE_KEYS}
    if scope["label_value"] not in LABEL_VALUES:
        raise PolicyError("label_value는 %s 중 하나" % (LABEL_VALUES,))
    cap_r = ratio(cap)
    if not 0 < cap_r <= ERROR_CAP:
        raise PolicyError("오류율 상한은 0 초과 %s 이하(D-3)" % ERROR_CAP)
    if not isinstance(confirm, dict):
        raise PolicyError("confirm은 dict여야 한다")
    n, errors = confirm.get("n"), confirm.get("errors")
    ints =isinstance(n, int) and isinstance(errors, int) and not isinstance(n, bool) and not isinstance(errors, bool)
    if not (isinstance(confirm.get("batch_id"), str) and confirm["batch_id"] and ints and 0 <= errors <= n):
        raise PolicyError("confirm에는 batch_id·n·errors(0 ≤ errors ≤ n)가 필요하다")
    if not isinstance(min_n, int) or isinstance(min_n, bool) or min_n < 1:
        raise PolicyError("min_n은 1 이상의 정수(사전 등록 값)")
    if confirm.get("role") != "confirm":
        return {"ok": False, "reason": "tune_batch_not_allowed"}  # 조정용 묶음에 맞춘 정책은 확인용으로만 판정한다
    with silver_store.lock(root):
        state = fold(silver_store.load(root))
        found = active_policy(state, scope)
        if found is not None:
            return {"ok": False, "reason": "already_approved", "policy_id": found["policy_id"]}
        silver_store.append(root, now, "calibration_used", {"batch_id": confirm["batch_id"], "role": "confirm", "scope": scope,
                                                            "n": n, "errors": errors})
        uses = state["uses"].get(confirm["batch_id"], 0) + 1
        if n < min_n:
            return {"ok": False, "reason": "too_few_regions", "confirm_uses": uses}
        if Fraction(errors, n) > cap_r:
            return {"ok": False, "reason": "error_rate_over_cap", "confirm_uses": uses}
        version = 1 + sum(1 for p in state["policies"].values() if p["scope"] == scope)
        key = "|".join(scope[k] for k in SCOPE_KEYS)
        policy_id = "pol-%s-v%d" % (hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], version)
        silver_store.append(root, now, "policy_approved", {"policy_id": policy_id, "scope": scope, "version": version, "cap": str(cap_r),
                                                           "n": n, "errors": errors, "confirm_batch_id": confirm["batch_id"]})
    return {"ok": True, "policy_id": policy_id, "error_rate": [errors, n], "confirm_uses": uses}


def grade_transition(current, target, created_by):
    """등급 전이 규칙. 허용되면 target을 돌려주고 아니면 PolicyError.

    AI(agent) 라벨은 어떤 검증을 거쳐도 Gold가 되지 않는다. Silver→Gold는 사람이 만든 라벨이라도 금지(Gold는 사람이 처음부터 만든 것만).
    판단 불가·미검증은 Pending이며 Pending→Silver는 품질 관문을 통과할 때만 쓴다. Gold는 바뀌지 않는다.
    """
    if created_by not in ("agent", "human"):
        raise PolicyError("created_by는 agent 또는 human")
    if target == "Gold" and created_by != "human":
        raise PolicyError("AI 라벨은 Gold가 될 수 없다")
    if current == "Silver" and target == "Gold":
        raise PolicyError("Silver→Gold 전이는 금지다")
    if (current, target) not in _ALLOWED:
        raise PolicyError("허용되지 않은 등급 전이: %r → %r" % (current, target))
    return target


def reject_prefilled(screen):
    """라벨 요청 화면·항목에 예측·후보를 미리 채운 필드가 있으면 PolicyError(앵커링 금지). 없으면 입력을 그대로 돌려준다.

    중첩된 dict·list를 모두 살핀다(재귀 대신 스택). 필드 이름 목록(PREFILL_KEYS)으로만 판단하므로 다른 이름으로 숨긴 미리 채움은 못 잡는다.
    """
    stack = [("screen", screen)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                # 0·0.0은 False와 같다고 비교되지만 채워진 값이다
                blank = value is None or value is False or (isinstance(value, (str, list, dict)) and not value)
                if str(key).lower() in PREFILL_KEYS and not blank:
                    raise PolicyError("미리 채운 입력은 거절한다: %s.%s" % (path, key))
                stack.append(("%s.%s" % (path, key), value))
        elif isinstance(node, (list, tuple)):
            stack.extend(("%s[%d]" % (path, i), item) for i, item in enumerate(node))
    return screen
