"""작업 상태 분류. 5개 상태(DESIGN 9절)와 보조 상태 2개(PENDING=큐에 있고 기록 없음, UNREGISTERED=큐에 없음).

작업 폴더: contract.json, out/(산출물), done.json(완료 기록+manifest), lease.json(작업권),
failures/NNN-<run_id>.json(실패 기록, 추가만).
"""
import os
import re

from . import lease
from .contract import RUN_ID, ContractError, task_key
from .jsonio import read_json
from .manifest import mismatches

VERIFIED, RUNNING, INTERRUPTED, FAILED, CORRUPT = "VERIFIED", "RUNNING", "INTERRUPTED", "FAILED", "CORRUPT"
PENDING, UNREGISTERED = "PENDING", "UNREGISTERED"
_FAILURE_FILE = re.compile(r"\d{3}-%s\.json" % RUN_ID.pattern)


def failures(task_dir):
    """실패 기록(오래된 순). 형식이 맞는 파일만 센다(임시 파일 무시). 읽을 수 없는 기록은 결정적 실패로 본다."""
    fdir = os.path.join(task_dir, "failures")
    found = []
    for name in sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []:
        if not _FAILURE_FILE.fullmatch(name):
            continue
        try:
            found.append(read_json(os.path.join(fdir, name)))
        except ValueError:
            found.append({"kind": "deterministic", "error": "읽을 수 없는 실패 기록: %s" % name})
    return found


def load_contract(task_dir):
    """contract.json. 없으면 None. 있으나 손상·폴더명과 task_key 불일치·outputs 비어 있음이면 ContractError."""
    path = os.path.join(task_dir, "contract.json")
    if not os.path.exists(path):
        return None
    try:
        task = read_json(path)
        intact = isinstance(task, dict) and task_key(task) == os.path.basename(task_dir) and bool(task["outputs"])
    except (ValueError, KeyError, TypeError):
        intact = False
    if not intact:
        raise ContractError("계약 파일이 손상되었거나 task_key와 맞지 않는다: %s" % path)
    return task


def classify(task_dir, now, is_alive):
    """완료 기록+산출물 해시 -> VERIFIED/CORRUPT, 작업권 -> RUNNING/INTERRUPTED, 실패 기록 -> FAILED.

    now는 쓰지 않는다(시계가 아니라 작업권 생존만으로 판정). 입력 해시가 같다는 것만으로는 VERIFIED가 아니다.
    작업권의 run_id가 마지막 실패 기록의 run_id와 같으면 FAILED다(실패 기록 직후 작업권 해제 전에 죽은 경우).
    """
    try:
        task = load_contract(task_dir)
    except ContractError:
        return CORRUPT
    if task is None:
        return UNREGISTERED
    done_path = os.path.join(task_dir, "done.json")
    if os.path.exists(done_path):
        try:
            done = read_json(done_path)
        except ValueError:
            return CORRUPT
        recorded = done.get("manifest") if isinstance(done, dict) else None
        return CORRUPT if mismatches(os.path.join(task_dir, "out"), recorded, task["outputs"]) else VERIFIED
    held = lease.read(os.path.join(task_dir, "lease.json"))
    records = failures(task_dir)
    if held is not None:
        if records and held.get("run_id") == records[-1].get("run_id"):
            return FAILED
        return RUNNING if is_alive(held) else INTERRUPTED
    return FAILED if records else PENDING
