"""Champion 포인터와 전환(승격·복원·Champion 없음 전환)과 개발용 Baseline 지정.

전환은 선기록(WAL)이다: registry에 switch_intent를 쓰고 → 포인터 파일을 원자 교체하고(임시 파일+fsync+os.replace+디렉터리 fsync)
→ switched를 쓰고 → 주 장부(root/ledger.jsonl)에 요약을 쓴다. 어느 지점에서 kill -9를 맞아도 포인터는 이전 또는 새 Champion(또는 "없음")을
완전하게 가리키고, 다음 호출의 settle이 포인터와 의도를 대조해 switched를 마저 쓰거나 switch_aborted를 쓴다.
주 장부 요약은 상태 변경 뒤에 쓰므로(1단계 가정 9와 같음) 죽으면 빠질 수 있다. 정본은 registry와 포인터다.
호출 깊이를 낮추려고 _switch와 settle의 장부 쓰기는 일부러 펼쳐 두었다.

잠금 순서: 승격·복원·철회(withdrawal.withdraw)는 모두 silver_store.lock → registry.lock 순서로 잡고, 그 안에서 두 장부를 읽어
eligibility의 같은 적격성 계산을 쓴다(호출자가 준 감사 상태는 받지 않는다). 레지스트리만 바꾸는 register·set_dev_baseline은 registry.lock만 잡는다.
읽기 규약: 잠금을 쥐지 않은 읽는 쪽은 `read_current(root)`를 쓴다. `current(root, state)`는 같은 잠금 안에서 load한 state와만 쓴다(pointer.py 참조).
"""
import os

from harness import cas, eligibility, gate, jsonio, ledger, pointer, registry, silver_store

_DONE = {"promote": "champion_promoted", "restore": "champion_restored", "clear": "champion_cleared"}
ChampionError = pointer.ChampionError
current = pointer.current  # 읽기 규약은 pointer.py docstring 참조(잠금 안에서 load한 state와만 쓴다)
read_current = pointer.read_current  # 잠금 없이 읽는 쪽은 이것을 쓴다


def settle(root, now, state):
    """죽은 전환의 마무리(registry.lock 안에서만): kill로 남은 임시 파일을 지우고, 짝 없는 switch_intent를 포인터와 대조해
    switched(포인터가 이미 바뀜) 또는 switch_aborted(안 바뀜)를 쓴다. 장부를 썼으면 True."""
    pointer.clean_tmp(root)
    pending = state["pending"]
    if pending is None:
        return False
    try:
        found = jsonio.read_json(os.path.join(root, registry.POINTER))
    except ValueError as err:
        raise ChampionError("Champion 포인터가 손상됨: %s" % err)
    swapped = isinstance(found, dict) and found.get("intent_hash") == pending["hash"]
    info = {"intent_hash": pending["hash"], "target": pending["target"], "from": pending["from"],
            "reason": pending["reason"]}
    if not swapped:
        ledger.append(os.path.join(root, registry.REGISTRY), now, "switch_aborted", info)
        return True
    ledger.append(os.path.join(root, registry.REGISTRY), now, "switched", dict(info, settled=True))
    ledger.append(os.path.join(root, "ledger.jsonl"), now, _DONE[pending["reason"]], dict(info, settled=True))
    return True


def _switch(root, now, state, target, reason, previous):
    """선기록 → 포인터 원자 교체 → 완료 기록. 반환값 없음(호출자는 필요하면 다시 load한다)."""
    reg = os.path.join(root, registry.REGISTRY)
    intent = ledger.append(reg, now, "switch_intent", {"target": target, "from": previous, "reason": reason})
    pointer_path = os.path.join(root, registry.POINTER)
    weights_sha = None if target is None else state["models"][target]["weights_sha"]  # target None = Champion 없음
    jsonio.write_json(pointer_path, {"model_id": target, "intent_hash": intent["hash"], "reason": reason, "weights_sha": weights_sha})
    fd = os.open(os.path.dirname(pointer_path), os.O_RDONLY)  # 이름 교체 자체를 디스크에 고정
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    info = {"intent_hash": intent["hash"], "target": target, "from": previous, "reason": reason}
    ledger.append(reg, now, "switched", info)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, _DONE[reason], info)


def promote(root, now, model_id):
    """model_id를 Champion으로 승격한다. 거절은 {"ok": False, "reason", "detail"}, 성공은 {"ok": True, ...}.

    적격성은 잠금 안에서 Silver 장부와 레지스트리를 직접 읽어 eligibility.model_reason으로 판정한다(감사 상태 인자는 없다: 호출자가 준 값을
    믿지 않는다). 그다음 구조 조건(gate.check). 이미 그 모델이 적격한 현재 Champion이면 아무 것도 쓰지 않고 already=True(멱등).
    """
    with silver_store.lock(root), registry.lock(root):
        facts = eligibility.silver_facts(silver_store.load(root))
        state = registry.load(root)
        if settle(root, now, state):
            state = registry.load(root)
        holder = current(root, state)
        verdict = eligibility.model_reason(state, facts, eligibility.manifest_reasons(root, state, facts), model_id)
        verdict = verdict or gate.check(root, state, model_id, holder)
        if verdict is not None:
            return dict(verdict, ok=False)
        if holder is not None and holder["model_id"] == model_id:
            return {"ok": True, "already": True, "model_id": model_id}
        previous = holder["model_id"] if holder else None
        _switch(root, now, state, model_id, "promote", previous)
    return {"ok": True, "already": False, "model_id": model_id, "previous": previous}


def restore_locked(root, now, state, facts, manifests):
    """두 잠금(silver → registry) 안에서 호출한다. 현재 Champion이 무효이면, 이전 Champion 중 승격과 같은 적격성 계산
    (eligibility.model_reason: 무효·파생 무효·철회 보류·manifest·감사)을 통과한 가장 최근 모델로 되돌린다. 보류 모델은 후보가 아니다.
    후보가 없으면 미검증 모델을 고르지 않고 "Champion 없음"으로 전환한다(같은 WAL, 포인터가 무효 모델을 계속 가리키지 않는다)."""
    holder = current(root, state)
    if holder is None:
        return {"ok": False, "reason": "no_champion"}
    if holder["valid"]:
        return {"ok": False, "reason": "champion_valid"}
    target = next((h["model_id"] for h in reversed(state["history"]) if h["model_id"] not in (None, holder["model_id"])
                   and eligibility.model_reason(state, facts, manifests, h["model_id"]) is None), None)
    if target is None:
        _switch(root, now, state, None, "clear", holder["model_id"])
        return {"ok": False, "reason": "no_verified_champion", "cleared": True, "restored_from": holder["model_id"]}
    # 포인터를 바꾸기 전에 CAS에서 가중치를 꺼내 기록된 해시와 다시 대조한다(재현 확인). 호출 깊이를 줄이려고 여기에 펼쳤다.
    record = state["models"][target]
    path = os.path.join(root, "models", "restored", record["model_id"], "weights")
    try:
        cas.get(os.path.join(root, "cas"), record["weights_sha"], path)
    except cas.CasError as err:
        raise ChampionError("복원할 가중치를 CAS에서 꺼낼 수 없음: %s" % err)
    if cas.sha_file(path) != record["weights_sha"]:
        os.unlink(path)
        raise ChampionError("복원 가중치 해시 불일치: %s" % record["model_id"])
    _switch(root, now, state, target, "restore", holder["model_id"])
    return {"ok": True, "model_id": target, "restored_from": holder["model_id"], "weights_path": path,
            "weights_sha": state["models"][target]["weights_sha"], "reproduced": True}


def restore_last_verified(root, now, regression=None, model_id=None):
    """현재 Champion이 무효이면 마지막 검증된 Champion으로 복원한다.

    regression(사유 문자열)을 주면 model_id(필수)가 현재 유효한 Champion일 때만 그 사유로 무효화한 뒤 복원한다. 현재 Champion이 다른 모델이면
    (예: 직전 호출이 이미 복원했다면) 무효화하지 않으므로 같은 인자로 재호출해도 새 Champion을 해치지 않는다(멱등).
    """
    if regression is not None and not (isinstance(model_id, str) and model_id):
        raise ChampionError("regression을 주려면 무효화할 model_id가 필요하다")
    with silver_store.lock(root), registry.lock(root):
        facts = eligibility.silver_facts(silver_store.load(root))
        state = registry.load(root)
        if settle(root, now, state):
            state = registry.load(root)
        holder = current(root, state)
        if regression is not None and holder is not None and holder["valid"] and holder["model_id"] == model_id:
            data = {"models": [model_id], "cause": "regression: %s" % (regression,)}
            registry.apply(state, ledger.append(os.path.join(root, registry.REGISTRY), now, "invalidated", data))
            ledger.append(os.path.join(root, "ledger.jsonl"), now, "champion_invalidated", data)
        return restore_locked(root, now, state, facts, eligibility.manifest_reasons(root, state, facts))


def set_dev_baseline(root, now, model_id, basis):
    """탐색 개발의 비교 기준(개발용 Baseline)을 명시한다. Champion이 아니고 승격·복원·부모 적격성의 근거가 아니다(eligibility는 읽지 않는다).

    자신과 조상이 레지스트리에서 무효가 아닌 모델만 받는다(보류 모델은 받는다: 탐색·원인 분석용 보존). 같은 모델·근거면 쓰지 않는다(멱등).
    """
    if not isinstance(basis, str) or not basis.strip():
        raise ChampionError("개발용 Baseline 지정에는 근거(문자열)가 필요하다")
    with registry.lock(root):
        state = registry.load(root)
        models = state["models"]
        if model_id not in models:
            return {"ok": False, "reason": "unknown_model", "detail": model_id}
        bad = [m for m in gate.ancestors(models, model_id) if models[m]["status"] != "valid"]
        if bad:
            return {"ok": False, "reason": "invalidated", "detail": bad}
        if state["dev_baseline"] == {"model_id": model_id, "basis": basis}:
            return {"ok": True, "already": True, "model_id": model_id}
        ledger.append(os.path.join(root, registry.REGISTRY), now, "dev_baseline_set", {"model_id": model_id, "basis": basis})
    return {"ok": True, "already": False, "model_id": model_id}
