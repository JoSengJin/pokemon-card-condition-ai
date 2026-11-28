"""모델 상향 `escalate()`와 상향 때 넘길 컨텍스트 필터. 상향은 원인이 분류된 품질·검증·불일치 실패에만 한 단계씩 한다."""

_KEEP_FAILURE = ("cause", "failure_kind", "signature", "error", "result")


def _eligible(decision, failure):
    """(상향 가능 여부, 사유). 원인 분류가 없거나 transient·데이터 부족·이미지 품질·코드 오류면 올리지 않는다."""
    cause = failure.get("cause") if isinstance(failure, dict) else None
    if not decision["needs_llm"]:
        return False, "모델을 쓰지 않는 작업: 상향 대상 아님"
    if not isinstance(cause, str) or not cause:
        return False, "원인 분류 없음: 상향하지 않음"
    if failure.get("failure_kind") == "transient":
        return False, "transient 실패(%s): 재시도 대상이며 상향하지 않음" % cause
    if cause in decision["no_escalate_causes"]:
        return False, "원인 %s는 모델 상향으로 풀리지 않음(원인 먼저 해결)" % cause
    if cause not in decision["escalate_causes"]:
        return False, "정책에 없는 원인 %s: 추정하지 않고 상향하지 않음" % cause
    if not decision["escalation_order"]:
        return False, "상향 순서 없음(정책 없음): 상향하지 않음"
    return True, cause


def _top(new, xhigh_justified, budget_remaining, learning_value_high):
    """최상위에서의 실패: 조건이 맞으면 Xhigh를 한 번, 아니면 Pending."""
    budget_ok = isinstance(budget_remaining, (int, float)) and not isinstance(budget_remaining, bool) \
        and budget_remaining > 0
    if new["xhigh"] and not new["xhigh_used"] and xhigh_justified is True and budget_ok:
        new["escalations"].append({"from": {"model": new["model"], "effort": new["effort"]},
                                   "to": dict(new["xhigh"]), "cause": new["reason"]})
        new.update(model=new["xhigh"]["model"], effort=new["xhigh"]["effort"], xhigh_used=True,
                   level=len(new["escalation_order"]), escalated=True,
                   reason="Opus High에서도 미해결: Xhigh 1회(필요성 확인·예산 남음)")
        return
    new.update(pending=True, request_user=learning_value_high is True, escalated=False,
               reason="최상위 모델로도 미해결: Pending 처리" + (
                   "(학습 가치 높음: 사용자 요청 대상)" if learning_value_high is True else "(사용자 요청 안 함)"))


def escalate(decision, failure, xhigh_justified=False, budget_remaining=None, learning_value_high=False):
    """한 단계 상향한 새 결정(원본은 바꾸지 않음). 올리지 않으면 escalated=False와 사유를 돌려준다.

    상향하면 이전 applied·limitations는 지운다(새 모델·effort에 대한 지원 확인을 다시 해야 하므로).
    """
    new = dict(decision, escalations=list(decision["escalations"]), escalated=False)
    new.pop("applied", None)
    new.pop("limitations", None)
    ok, why = _eligible(decision, failure)
    if not ok:
        new["reason"] = why
        return new
    chain, level = new["escalation_order"], new["level"]
    if level is not None and level >= len(chain) - 1:
        new["reason"] = why  # _top이 사유를 쓴다(상향 기록의 cause로 보존)
        _top(new, xhigh_justified, budget_remaining, learning_value_high)
        return new
    target = chain[0 if level is None else level + 1]
    new["escalations"].append({"from": {"model": new["model"], "effort": new["effort"]},
                               "to": dict(target), "cause": why})
    new.update(model=target["model"], effort=target["effort"], level=chain.index(target), escalated=True,
               reason="상향(%s): %s/%s → %s/%s" % (why, decision["model"], decision["effort"],
                                              target["model"], target["effort"]))
    return new


def context_for_escalation(context, evidence_keys, failure):
    """상향 모델에 넘길 입력: 해당 작업의 근거 키와 실패 결과만. 나머지 키는 이름만 dropped로 남기고 값은 넘기지 않는다."""
    if not isinstance(context, dict) or not isinstance(evidence_keys, (list, tuple)) \
            or not all(isinstance(k, str) for k in evidence_keys):
        raise ValueError("context는 dict, evidence_keys는 문자열 목록이어야 한다")
    keep = [k for k in evidence_keys if k in context]
    return {
        "evidence": {k: context[k] for k in keep},
        "missing": [k for k in evidence_keys if k not in context],
        "failure": {k: v for k, v in failure.items() if k in _KEEP_FAILURE} if isinstance(failure, dict) else None,
        "dropped": sorted(set(context) - set(keep)),
    }
