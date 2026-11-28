"""Champion 포인터 읽기와 대조, 임시 파일 정리.

읽기 규약: `current(root, state)`는 state가 포인터와 같은 시점의 레지스트리여야 한다(registry.lock 안에서 load한 것).
잠금 없이 `registry.load` 뒤에 `current`를 부르면 그 사이 다른 프로세스가 승격해 거짓 ChampionError가 난다.
잠금을 쥐지 않은 읽는 쪽은 `read_current(root)`를 쓴다(잠금을 잡고 load와 current를 한 번에 한다. 승격이 끝나는 짧은 시간만 기다린다).
"""
import os

from harness import jsonio, registry


class ChampionError(Exception):
    pass


def current(root, state):
    """포인터가 가리키는 Champion {model_id, intent_hash, weights_sha, valid}. 포인터가 없고 승격 기록도 없으면 None,
    마지막 전환이 "Champion 없음"(대상 None, 사유 clear)이면 None이다.

    포인터는 마지막으로 완료된 전환(history[-1]) 또는 대기 중인 의도(pending, 포인터는 바뀌었으나 switched를 쓰기 전에 죽은 경우)의
    (의도 해시, 대상 모델)과 정확히 같아야 한다. 다른 등록 모델로 바꾼 포인터, 의도가 아닌 줄의 해시를 가리키는 포인터, 오래된 포인터
    파일로의 되돌림, 승격 기록이 있는데 포인터가 없는 경우, 가중치 해시가 다른 포인터는 모두 ChampionError다(조용히 넘어가지 않는다).
    """
    try:
        found = jsonio.read_json(os.path.join(root, registry.POINTER))
    except ValueError as err:
        raise ChampionError("Champion 포인터가 손상됨: %s" % err)
    if found is None:
        if state["history"]:
            raise ChampionError("승격 기록이 있는데 포인터가 없다")
        return None
    last = state["history"][-1:]
    allowed = [(h["intent_hash"], h["model_id"]) for h in last]
    if state["pending"] is not None:
        allowed.append((state["pending"]["hash"], state["pending"]["target"]))
    ok = isinstance(found, dict) and (found.get("intent_hash"), found.get("model_id")) in allowed
    if ok and found["model_id"] is None:
        return None
    if not ok or found.get("weights_sha") != state["models"][found["model_id"]]["weights_sha"]:
        raise ChampionError("포인터가 레지스트리의 마지막 전환과 맞지 않음: %r" % (found,))
    return dict(found, valid=state["models"][found["model_id"]]["status"] == "valid")


def read_current(root):
    """잠금 없이 읽는 쪽용: 잠금 안에서 레지스트리와 포인터를 같은 시점으로 읽는다. 쓰기는 하지 않는다."""
    with registry.lock(root):
        return current(root, registry.load(root))


def clean_tmp(root):
    """models/ 아래에 kill로 남은 `*.tmp.<pid>` 임시 파일(포인터·복원 가중치)을 지운다. registry.lock 안에서만 부른다."""
    removed = []
    for folder, _, names in os.walk(os.path.join(root, "models")):
        for name in names:
            if ".tmp." in name:
                os.unlink(os.path.join(folder, name))
                removed.append(os.path.join(folder, name))
    return removed
