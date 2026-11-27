"""사람 Gold 저장소(DESIGN 5-2·13절). root/gold/store.jsonl 한 개의 추가 전용 해시 체인(1단계 ledger).

- 저장 한 건 = 장부 한 줄. 그 줄이 확정 지점이며, nonce 사용 여부와 완료 키는 모두 이 줄들에서 계산한다.
- 원문은 훅이 받은 prompt의 UTF-8 바이트를 base64로 둔다. 1단계 장부는 read().splitlines()로 줄을 나누므로
  U+2028·U+2029·U+0085가 든 문자열을 그대로 넣으면 장부가 손상된다.
- 저장소는 파싱한 값을 받지 않고 훅 입력의 원문을 직접 파싱한다(저장한 답과 원문이 어긋날 수 없게).
- 출처는 human으로 고정이고 호출자가 바꾸는 인자가 없다. AI 라벨은 이 저장소에 넣지 않는다. human은 "직접판정=확인"
  칸의 자기 신고에 근거하며, 실제로 사람이 판정했는지는 이 코드가 확인할 수 없다.
- fail-closed: save는 이 프로세스의 __main__이 훅 진입점 파일일 때만 쓴다. 훅이 없으면 아무것도 저장되지 않는다.

한계(정직하게): 위 표식은 에이전트가 save를 직접 import해 부르는 실수·우회 시도를 막을 뿐 보안 경계가 아니다.
같은 사용자 권한이면 진입점에 모의 JSON을 파이프로 넣거나, __main__.__file__을 바꾸거나, 장부 파일을 직접 쓰거나
통째로 다시 써서 위조할 수 있다. 감지 수단과 범위:
  (1) audit(): 체인 손상, 발급 없는 기록, 원문·해시·답의 불일치, nonce 재사용, 완료 키 중복.
      꼬리 삭제와 전체 재작성은 밖에 복제해 둔 마지막 해시(store_tail·issued_tail)가 있어야만 감지한다.
  (2) Claude 대화 기록 대조: 기록의 session_id·transcript_path·원문 sha256으로, 그 원문이 실제 사용자 메시지였는지
      확인할 수 있다. 이 대조 도구는 아직 없고(대화 기록 형식 미확인), 대화 기록도 같은 권한으로 고칠 수 있다.
  규칙을 모두 맞춰 만든 위조(진입점에 파이프로 넣은 경우 포함)는 audit()만으로는 구별하지 못한다.
"""
import base64
import fcntl
import hashlib
import json
import os
import sys

from . import gold_parse, ledger
from .gold_parse import GoldError

ISSUED = os.path.join("gold", "issued.jsonl")
STORE = os.path.join("gold", "store.jsonl")
ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks", "user_prompt_submit.py")
EVENT = "gold_received"


def rows(root, name):
    """체인을 검증하고 장부 줄을 돌려준다(없으면 빈 목록). 손상은 GoldError(고치거나 건너뛰지 않는다)."""
    path = os.path.join(root, name)
    problems = ledger.verify(path)
    if problems:
        raise GoldError("chain_broken", "%s %d번째 줄 %s" % (name, problems[0]["line"], problems[0]["problem"]))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle.read().splitlines()]
    except FileNotFoundError:
        return []


def _derive(issued, raw):
    """발급 줄과 원문 바이트만으로 정해지는 기록 칸. save가 쓰고 audit가 다시 계산해 대조한다."""
    answer, screen = gold_parse.parse(raw.decode("utf-8")), issued["data"]
    if screen["screen_id"] != answer["screen_id"] \
            or screen["nonce_sha256"] != hashlib.sha256(answer["nonce"].encode("ascii")).hexdigest():
        raise GoldError("not_issued", "발급 기록에 없는 화면·nonce 조합")
    if set(answer["answers"]) != set(screen["zones"]):
        lost, extra = set(screen["zones"]) - set(answer["answers"]), set(answer["answers"]) - set(screen["zones"])
        raise GoldError("zone_mismatch", "빠짐 %d개, 화면에 없음 %d개" % (len(lost), len(extra)))
    return {"source": "human", "screen_id": screen["screen_id"], "nonce": answer["nonce"],
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_b64": base64.b64encode(raw).decode("ascii"),
            "submitted_at": answer["submitted_at"], "judge_confirmation": answer["confirm"], "judge": screen["judge"],
            "criteria_version": screen["criteria_version"], "planned_repeat": screen["planned_repeat"],
            "issued_hash": issued["hash"],
            "items": [dict(zone, zone=name, value=answer["answers"][name]) for name, zone in sorted(screen["zones"].items())]}


def completed(record):
    """이 기록이 판정을 끝낸 (이미지 SHA, 구역, 기준 판본, 판정자) 키. "미확인"은 완료가 아니다."""
    return {(i["image_sha256"], i["region"], record["criteria_version"], record["judge"])
            for i in record["items"] if i["value"] != gold_parse.UNJUDGED}


def save(root, payload, now):
    """훅 입력(dict)의 Gold 붙여넣기를 한 번만 저장하고 장부 줄을 돌려준다. 거절은 GoldError(아무것도 쓰지 않는다)."""
    main = getattr(sys.modules.get("__main__"), "__file__", None)
    if not main or os.path.realpath(main) != os.path.realpath(ENTRY):
        raise GoldError("no_hook_mark", "UserPromptSubmit 훅 진입점을 거치지 않은 저장")
    if payload.get("hook_event_name") != "UserPromptSubmit" or not isinstance(payload.get("prompt"), str):
        raise GoldError("no_hook_mark", "UserPromptSubmit 입력이 아님")
    answer = gold_parse.parse(payload["prompt"])
    raw = payload["prompt"].encode("utf-8")
    os.makedirs(os.path.join(root, "gold"), exist_ok=True)
    with open(os.path.join(root, "gold", ".lock"), "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)  # 읽기 → 판단 → 추가를 직렬화. 프로세스가 죽으면 풀린다
        issued = [r for r in rows(root, ISSUED) if r["data"]["screen_id"] == answer["screen_id"]]
        if len(issued) != 1:
            raise GoldError("not_issued", "발급 기록에 없는 화면")
        record = _derive(issued[0], raw)
        stored = [r["data"] for r in rows(root, STORE)]
        if any(old["nonce"] == record["nonce"] for old in stored):
            raise GoldError("nonce_reused", "이미 저장에 쓴 nonce")
        if not record["planned_repeat"]:
            done = set().union(*(completed(old) for old in stored))
            again = [i["zone"] for i in record["items"]
                     if (i["image_sha256"], i["region"], record["criteria_version"], record["judge"]) in done]
            if again:
                raise GoldError("completed_key", "이미 끝난 판정: %s(화면 전체를 저장하지 않음)" % ", ".join(again))
        # 대화 기록 대조용. 줄바꿈 문자가 든 값은 장부를 깨뜨리므로 남기지 않는다.
        for key in ("session_id", "transcript_path"):
            value = payload.get(key)
            record[key] = value if isinstance(value, str) and value.isprintable() else None
        record["received_at"] = now
        return ledger.append(os.path.join(root, STORE), now, EVENT, record)


def audit(root, issued_tail=None, store_tail=None):
    """문제 목록(빈 목록이면 이 검사에서 발견한 것이 없음. 위조가 없다는 증명은 아니다). Gold를 읽는 쪽이 먼저 부른다."""
    problems = [dict(p, file=name) for name, tail in ((ISSUED, issued_tail), (STORE, store_tail))
                for p in ledger.verify(os.path.join(root, name), tail)]
    if problems:
        return problems
    issued = {r["data"]["screen_id"]: r for r in rows(root, ISSUED)}
    nonces, done = set(), set()
    for entry in rows(root, STORE):
        data, found = entry["data"], []
        try:
            want = _derive(issued[data["screen_id"]], base64.b64decode(data["raw_b64"], validate=True))
            extra = {"session_id", "transcript_path", "received_at"}
            if entry["event"] != EVENT or set(data) != set(want) | extra or any(data[k] != v for k, v in want.items()):
                found.append("record_differs_from_raw_or_issue")
            if data["nonce"] in nonces:
                found.append("nonce_reused")
            if not data["planned_repeat"] and completed(data) & done:
                found.append("completed_key_repeated")
            nonces.add(data["nonce"])
            done |= completed(data)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            found.append("invalid_record:%s" % (error.args[0] if isinstance(error, GoldError) else type(error).__name__))
        problems.extend({"file": STORE, "seq": entry["seq"], "problem": p} for p in found)
    return problems
