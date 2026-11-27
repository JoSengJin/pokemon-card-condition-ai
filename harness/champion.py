"""Champion 포인터와 전환(승격·복원).

전환은 선기록(WAL)이다: registry에 switch_intent를 쓰고 → 포인터 파일을 원자 교체하고(임시 파일+fsync+os.replace+디렉터리 fsync)
→ switched를 쓰고 → 주 장부(root/ledger.jsonl)에 요약을 쓴다. 어느 지점에서 kill -9를 맞아도 포인터는 이전 또는 새 Champion을
완전하게 가리키고, 다음 호출의 settle이 포인터와 의도를 대조해 switched를 마저 쓰거나 switch_aborted를 쓴다.
주 장부 요약은 상태 변경 뒤에 쓰므로(1단계 가정 9와 같음) 죽으면 빠질 수 있다. 정본은 registry와 포인터다.
호출 깊이를 낮추려고 _switch와 settle의 장부 쓰기는 일부러 펼쳐 두었다.

읽기 규약: 쓰는 함수(promote·restore_last_verified·lineage.invalidate_lineage)는 모두 registry.lock 안에서 load → settle → 판단 → 쓰기를 한다.
잠금을 쥐지 않은 읽는 쪽은 `read_current(root)`를 쓴다. `current(root, state)`는 같은 잠금 안에서 load한 state와만 쓴다(pointer.py 참조).
"""
import os

from harness import cas, gate, jsonio, ledger, pointer, registry

_DONE = {"promote": "champion_promoted", "restore": "champion_restored"}
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
    jsonio.write_json(pointer_path, {"model_id": target, "intent_hash": intent["hash"], "reason": reason,
                                     "weights_sha": state["models"][target]["weights_sha"]})
    fd = os.open(os.path.dirname(pointer_path), os.O_RDONLY)  # 이름 교체 자체를 디스크에 고정
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    info = {"intent_hash": intent["hash"], "target": target, "from": previous, "reason": reason}
    ledger.append(reg, now, "switched", info)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, _DONE[reason], info)


def promote(root, now, model_id, audit_status=None):
    """model_id를 Champion으로 승격한다. 거절은 {"ok": False, "reason", "detail"}, 성공은 {"ok": True, ...}.

    이미 그 모델이 유효한 현재 Champion이면 아무 것도 쓰지 않고 already=True(멱등).
    audit_status: {Silver 묶음 ID: complete|not_required|pending|failed}. 계보 전체의 묶음이 모두 complete/not_required여야 한다.
    """
    if audit_status is None:
        audit_status = {}
    if not isinstance(audit_status, dict):
        raise ChampionError("audit_status는 dict여야 한다")
    with registry.lock(root):
        state = registry.load(root)
        if settle(root, now, state):
            state = registry.load(root)
        holder = current(root, state)
        if holder is not None and holder["model_id"] == model_id and holder["valid"]:
            return {"ok": True, "already": True, "model_id": model_id}
        verdict = gate.check(root, state, model_id, holder, audit_status)
        if verdict is not None:
            return dict(verdict, ok=False)
        previous = holder["model_id"] if holder else None
        _switch(root, now, state, model_id, "promote", previous)
    return {"ok": True, "already": False, "model_id": model_id, "previous": previous}


def restore_locked(root, now, state):
    """lock 안에서 호출한다. 현재 Champion이 무효이면 가장 최근의 다른 유효한 이전 Champion으로 되돌린다."""
    holder = current(root, state)
    if holder is None:
        return {"ok": False, "reason": "no_champion"}
    if holder["valid"]:
        return {"ok": False, "reason": "champion_valid"}
    models = state["models"]  # 후보는 자신과 모든 조상이 유효해야 한다(승격 관문과 같은 보수적 기준)
    target = next((h["model_id"] for h in reversed(state["history"]) if h["model_id"] != holder["model_id"]
                   and all(models[m]["status"] == "valid" for m in gate.ancestors(models, h["model_id"]))), None)
    if target is None:
        return {"ok": False, "reason": "no_verified_champion"}
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
    with registry.lock(root):
        state = registry.load(root)
        if settle(root, now, state):
            state = registry.load(root)
        holder = current(root, state)
        if regression is not None and holder is not None and holder["valid"] and holder["model_id"] == model_id:
            data = {"models": [model_id], "cause": "regression: %s" % (regression,)}
            registry.apply(state, ledger.append(os.path.join(root, registry.REGISTRY), now, "invalidated", data))
            ledger.append(os.path.join(root, "ledger.jsonl"), now, "champion_invalidated", data)
        return restore_locked(root, now, state)
