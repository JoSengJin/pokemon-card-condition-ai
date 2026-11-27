"""작업 상태 분류. 5개 상태(DESIGN 9절)와 보조 상태 2개(PENDING=큐에 있고 기록 없음, UNREGISTERED=큐에 없음).

작업 폴더: contract.json, out/(산출물), done.json(완료 기록+manifest), lease.json(작업권),
failures/NNN-<run_id>.json(실패 기록, 추가만), checkpoint.json.

호출 깊이 설계: 판정에 필요한 사실 수집(facts)과 판정(state_of)을 나눴다. facts는 말단 함수만 부르고
state_of·failures는 아무것도 부르지 않는다. 그래서 claim/recover/register_missing이 facts → state_of를 직접
부르면 깊이가 2다. classify는 같은 순서를 한 번 감싼 관찰자용 진입점이다.
"""
import json
import os
import re

from . import lease
from .cas import sha_file
from .contract import RUN_ID, task_key
from .jsonio import read_json
from .manifest import safe_path

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
            with open(os.path.join(fdir, name), "r", encoding="utf-8") as handle:
                found.append(json.load(handle))
        except ValueError:
            found.append({"kind": "deterministic", "error": "읽을 수 없는 실패 기록: %s" % name})
    return found


def facts(task_dir):
    """판정에 필요한 사실(읽기만 한다). contract_state: absent|ok|bad, done_state: absent|ok|bad.

    bad: 완료 기록과 어긋난 산출물 상대 경로, restorable: CAS에서 되살릴 수 있는 (sha, 대상 경로) 목록,
    held: 작업권 기록(없음 None, 깨짐 {}), records: 실패 기록, checkpoint: 없음 None / 손상 "damaged", stopped: 중단 한도 정지 표식(없음 None).
    """
    found = {"contract": None, "contract_state": "absent", "done_state": "absent", "bad": [], "restorable": [],
             "held": lease.read(os.path.join(task_dir, "lease.json")), "records": failures(task_dir),
             "checkpoint": None, "stopped": None}
    path = os.path.join(task_dir, "contract.json")
    if os.path.exists(path):
        try:
            task = read_json(path)
            intact = isinstance(task, dict) and task_key(task) == os.path.basename(task_dir) and bool(task["outputs"])
        except (ValueError, KeyError, TypeError):
            task, intact = None, False
        found.update(contract=task if intact else None, contract_state="ok" if intact else "bad")
    try:
        found["checkpoint"] = read_json(os.path.join(task_dir, "checkpoint.json"))
    except ValueError:
        found["checkpoint"] = "damaged"
    try:
        found["stopped"] = read_json(os.path.join(task_dir, "stopped.json"))
    except ValueError:
        found["stopped"] = "damaged"
    done_path = os.path.join(task_dir, "done.json")
    if found["contract_state"] != "ok" or not os.path.exists(done_path):
        return found
    outputs, out_dir = found["contract"]["outputs"], os.path.join(task_dir, "out")
    try:
        done = read_json(done_path)
    except ValueError:
        done = None
    recorded = done.get("manifest") if isinstance(done, dict) else None
    found["done_state"] = "ok" if isinstance(done, dict) else "bad"
    if not isinstance(recorded, dict):
        found["bad"] = sorted(outputs)
        return found
    bad = set(recorded) ^ set(outputs)
    for rel in set(recorded) & set(outputs):
        target = safe_path(out_dir, rel)
        if target is None or os.path.islink(target) or not os.path.isfile(target) \
                or sha_file(target) != recorded[rel]:
            bad.add(rel)
            if target is not None and not os.path.islink(target):
                found["restorable"].append((recorded[rel], target))
    found["bad"] = sorted(bad)
    return found


def state_of(info, alive):
    """facts 결과와 작업권 생존 여부(alive)로 상태를 정한다. 아무것도 읽지·부르지 않는다.

    완료 기록+산출물 해시 -> VERIFIED/CORRUPT, 작업권 -> RUNNING/INTERRUPTED, 실패 기록 -> FAILED.
    입력 해시가 같다는 것만으로는 VERIFIED가 아니다. 작업권의 run_id가 마지막 실패 기록의 run_id와 같으면
    FAILED다(실패 기록 직후 작업권 해제 전에 죽은 경우).
    """
    if info["contract_state"] == "absent":
        return UNREGISTERED
    if info["contract_state"] == "bad" or info["done_state"] == "bad":
        return CORRUPT
    if info["done_state"] == "ok":
        return CORRUPT if info["bad"] else VERIFIED
    held, records = info["held"], info["records"]
    if held is not None:
        if records and held.get("run_id") == records[-1].get("run_id"):
            return FAILED
        return RUNNING if alive else INTERRUPTED
    return FAILED if records else PENDING


def classify(task_dir, now, is_alive):
    """관찰자용: facts를 읽고 작업권 생존(is_alive)을 확인해 상태를 돌려준다. now는 쓰지 않는다(시계 의존 판정 금지)."""
    info = facts(task_dir)
    return state_of(info, bool(info["held"] is not None and is_alive(info["held"])))
