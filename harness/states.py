"""작업 상태 분류. 5개 상태(DESIGN 9절)와 보조 상태 2개(PENDING=큐에 있고 기록 없음, UNREGISTERED=큐에 없음).

작업 폴더: contract.json, out/(산출물), done.json(완료 기록+manifest), lease.json(작업권),
failures/NNN-<run_id>.json(실패 기록, 추가만).
"""
import os

from . import lease
from .jsonio import read_json
from .manifest import mismatches

VERIFIED, RUNNING, INTERRUPTED, FAILED, CORRUPT = "VERIFIED", "RUNNING", "INTERRUPTED", "FAILED", "CORRUPT"
PENDING, UNREGISTERED = "PENDING", "UNREGISTERED"


def failures(task_dir):
    """실패 기록(오래된 순). 읽을 수 없는 기록은 결정적 실패로 본다(재시도 근거로 쓰지 않는다)."""
    fdir = os.path.join(task_dir, "failures")
    found = []
    for name in sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []:
        try:
            found.append(read_json(os.path.join(fdir, name)))
        except ValueError:
            found.append({"kind": "deterministic", "error": "읽을 수 없는 실패 기록: %s" % name})
    return found


def classify(task_dir, now, is_alive):
    """완료 기록+산출물 해시 -> VERIFIED/CORRUPT, 작업권 -> RUNNING/INTERRUPTED, 실패 기록 -> FAILED.

    now는 쓰지 않는다(시계가 아니라 작업권 생존만으로 판정). 입력 해시가 같다는 것만으로는 VERIFIED가 아니다.
    """
    task = read_json(os.path.join(task_dir, "contract.json"))
    if task is None:
        return UNREGISTERED
    try:
        done = read_json(os.path.join(task_dir, "done.json"))
    except ValueError:
        return CORRUPT
    if done is not None:
        recorded = done.get("manifest") if isinstance(done, dict) else None
        bad = mismatches(os.path.join(task_dir, "out"), recorded, task["outputs"])
        return CORRUPT if bad else VERIFIED
    held = lease.read(os.path.join(task_dir, "lease.json"))
    if held is not None:
        return RUNNING if is_alive(held) else INTERRUPTED
    return FAILED if failures(task_dir) else PENDING
