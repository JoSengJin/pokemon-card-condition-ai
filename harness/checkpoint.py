"""체크포인트 지문: 코드·자료 SHA, seed, 난수·옵티마이저·데이터 순서가 모두 같아야 복원할 수 있다."""
import os

from .jsonio import write_json

REQUIRED = ("code_sha", "data_sha", "seed", "rng", "optimizer", "data_order")


def save(task_dir, run_id, fingerprint, now):
    write_json(os.path.join(task_dir, "checkpoint.json"),
               {"run_id": run_id, "fingerprint": fingerprint, "saved_at": now})


def check(saved, run_id, current):
    """복원해도 되면 None, 아니면 그 이유(문자열). saved는 states.facts의 체크포인트(없음 None, 손상 "damaged")."""
    if not isinstance(current, dict) or any(current.get(k) is None for k in REQUIRED):
        return "현재 실행 지문이 없거나 불완전하다(복원 불가)"
    if saved == "damaged":
        return "체크포인트가 손상됨"
    if not isinstance(saved, dict) or saved.get("run_id") != run_id:
        return "체크포인트가 없거나 중단된 실행의 것이 아님"
    fingerprint = saved.get("fingerprint")
    if not isinstance(fingerprint, dict):
        return "체크포인트 지문이 손상됨"
    differs = [k for k in REQUIRED if fingerprint.get(k) is None or fingerprint.get(k) != current[k]]
    return "체크포인트 지문 불일치: %s" % ",".join(differs) if differs else None
