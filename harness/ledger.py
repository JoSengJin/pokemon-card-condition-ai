"""해시 체인 장부(JSONL). 줄: {seq, prev, ts, event, data, hash}. 추가만 하며 덮어쓰지 않는다.

hash = sha256(prev + canonical({seq, ts, event, data})). 꼬리 잘림은 외부에 복제한 마지막 해시
(expected_tail)와 대조할 때만 감지된다(복제본이 없으면 마지막 줄 삭제는 알 수 없다).
전체 줄을 처음부터 다시 계산해 쓴 위조(해시를 모두 재계산)도 expected_tail 복제본 없이는 감지되지 않는다.
"""
import fcntl
import hashlib
import json
import os

GENESIS = "0" * 64
_KEYS = {"seq", "prev", "ts", "event", "data", "hash"}


class LedgerError(Exception):
    pass


def append(path, ts, event, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        text = handle.read()
        # "\n"으로만 나눈다: splitlines()는 ensure_ascii=False로 그대로 쓰인 U+2028·U+2029·U+0085에서도 줄을 나눈다
        lines = text.removesuffix("\n").split("\n") if text else []
        prev, seq = GENESIS, 0
        if lines:
            try:
                last = json.loads(lines[-1])
                # 해시 계산을 여기에 펼쳤다(호출 깊이를 줄이려고. verify의 _check_line과 같은 식이며 어긋나면 append→verify 시험이 잡는다).
                last_body = json.dumps({"seq": last["seq"], "ts": last["ts"], "event": last["event"], "data": last["data"]},
                                       sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                intact = hashlib.sha256((last["prev"] + last_body).encode("utf-8")).hexdigest() == last["hash"]
            except (ValueError, KeyError, TypeError):
                intact = False
            if not intact:
                raise LedgerError("장부 마지막 줄이 손상되어 이어 쓰지 않는다")
            prev, seq = last["hash"], last["seq"] + 1
        body = json.dumps({"seq": seq, "ts": ts, "event": event, "data": data}, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        entry = {"seq": seq, "prev": prev, "ts": ts, "event": event, "data": data,
                 "hash": hashlib.sha256((prev + body).encode("utf-8")).hexdigest()}
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return []
    return text.removesuffix("\n").split("\n") if text else []  # append와 같은 나누기


def tail(path):
    """마지막 줄의 해시(외부 복제용). 비어 있으면 GENESIS."""
    lines = _load(path)
    return json.loads(lines[-1])["hash"] if lines else GENESIS


def _check_line(line_no, raw, want_seq, prev):
    """한 줄 검사 -> (문제 목록, 파싱한 항목 또는 None)."""
    try:
        entry = json.loads(raw)
        if not isinstance(entry, dict) or set(entry) != _KEYS:
            raise ValueError("형식")
    except ValueError:
        return [{"line": line_no, "seq": None, "problem": "unparseable"}], None
    found = []
    if entry["seq"] != want_seq:
        found.append("seq_mismatch")
    if entry["prev"] != prev:
        found.append("prev_mismatch")
    try:  # append와 같은 계산(호출 깊이를 줄이려고 펼쳤다. 어긋나면 append→verify 시험이 잡는다)
        body = json.dumps({"seq": entry["seq"], "ts": entry["ts"], "event": entry["event"], "data": entry["data"]},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        recomputed = hashlib.sha256((entry["prev"] + body).encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        recomputed = None
    if recomputed != entry["hash"]:
        found.append("hash_mismatch")
    return [{"line": line_no, "seq": entry["seq"], "problem": p} for p in found], entry


def verify(path, expected_tail=None):
    """문제 목록(빈 목록이면 정상). 각 문제는 줄 번호(line)·seq·종류(problem)를 가진다."""
    problems, prev, want = [], GENESIS, 0
    lines = _load(path)
    for line_no, raw in enumerate(lines, 1):
        found, entry = _check_line(line_no, raw, want, prev)
        problems.extend(found)
        want += 1
        if entry is not None:
            prev = entry["hash"]
            want = entry["seq"] + 1 if isinstance(entry["seq"], int) else want
    if expected_tail is not None and prev != expected_tail:
        problems.append({"line": len(lines), "seq": want - 1, "problem": "tail_mismatch"})
    return problems
