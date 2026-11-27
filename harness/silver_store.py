"""Silver 저장소: 정책·보정 사용·라벨·감사·재라벨 요청 이벤트를 한 개의 추가 전용 해시 체인(1단계 ledger)에 쓴다.

경로는 root/silver/store.jsonl. 쓰기 호출은 모두 lock(root) 안에서 load → 판단 → append 순서다(7단계 레지스트리와 같은 규약).
한 체인에 모으는 이유: 중간에 죽어도 항상 "앞부분 이벤트까지"인 한 가지 상태만 남고, 체인 하나만 검증하면 되기 때문이다.
호출 깊이를 낮추려고 load는 ledger.verify만 부르고 파싱은 직접 한다(호출자 → load → verify → _check_line → _hash_entry).
"""
import contextlib
import fcntl
import json
import os

from harness import ledger

STORE = os.path.join("silver", "store.jsonl")


class StoreError(Exception):
    pass


@contextlib.contextmanager
def lock(root):
    """Silver 저장소를 바꾸는 호출의 직렬화. 프로세스가 죽으면 flock이 풀린다."""
    path = os.path.join(root, "silver", ".lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def append(root, now, event, data):
    """이벤트 한 줄을 추가한다(fsync 포함). 반환은 장부 줄."""
    return ledger.append(os.path.join(root, STORE), now, event, data)


def load(root, expected_tail=None):
    """체인을 검증하고 이벤트 줄 목록을 돌려준다(파일이 없으면 빈 목록). 변조·손상은 StoreError(추정하지 않는다)."""
    path = os.path.join(root, STORE)
    problems = ledger.verify(path, expected_tail)
    if problems:
        raise StoreError("Silver 저장소 체인 손상: %s" % (problems[:3],))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle.read().splitlines()]
    except FileNotFoundError:
        return []
