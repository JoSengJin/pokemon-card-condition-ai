"""사람 Gold 저장소(DESIGN 5-2·13절). root/gold/store.jsonl 한 개의 추가 전용 해시 체인(1단계 ledger).

- 저장 한 건 = 장부 한 줄. 그 줄이 확정 지점이며, nonce 사용 여부와 완료 키는 모두 이 줄들에서 계산한다.
- 원문은 훅이 받은 prompt의 UTF-8 바이트를 base64로 둔다(바이트 그대로 보존). 장부 줄은 "\n"으로만 나눈다:
  값 안의 U+2028·U+2029·U+0085에서 splitlines()로 나누면 체인 검증을 통과한 장부도 읽지 못한다.
- 저장소는 파싱한 값을 받지 않고 훅 입력의 원문을 직접 파싱한다(저장한 답과 원문이 어긋날 수 없게).
- 출처는 human으로 고정이고 호출자가 바꾸는 인자가 없다. AI 라벨은 이 저장소에 넣지 않는다. human은 "직접판정=확인"
  칸의 자기 신고에 근거하며, 실제로 사람이 판정했는지는 이 코드가 확인할 수 없다.
- fail-closed: save는 이 프로세스의 __main__이 훅 진입점 파일일 때만 쓴다. 훅이 없으면 아무것도 저장되지 않는다.
- 발급 줄의 형식(valid_issue)은 발급·저장·audit이 같은 검사를 쓴다. 형식 밖 줄은 저장 근거가 되지 않고 audit가 알린다.
  형식을 모두 맞춰 장부에 직접 쓴 발급 줄은 issue()가 쓴 것과 구별하지 못한다.
- 현재 코드는 개발용 평문 채팅 경로다. 사용자 결정(2026-11-27, 설계 방향 합의이며 코드·설치 미승인): 이 경로는 봉인 Gold
  수집에 쓰지 않는다. 보호 구조(task 문서)는 구현하지 않았고, 검증 완료 전에는 봉인 Gold 수집·확증 평가를 하지 않는다.

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
import re
import sys
import time

from . import gold_parse, ledger
from .gold_parse import GoldError

ISSUED = os.path.join("gold", "issued.jsonl")
STORE = os.path.join("gold", "store.jsonl")
ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks", "user_prompt_submit.py")
EVENT = "gold_received"
ISSUE_EVENT = "gold_screen_issued"
ISSUE_KEYS = {"screen_id", "zones", "criteria_version", "judge", "planned_repeat", "nonce_sha256"}
ZONE_KEYS = {"image_sha256", "region", "crop_sha256"}  # crop_sha256: 그때 보여 준 사진 조각(label-provenance)
# 완료 키의 세 칸은 철자 하나만 허용한다(대소문자·구분자·보이지 않는 문자로 같은 판정을 새 키로 만들 수 없게).
# 정본: card_condition/regions.GLARE_AREAS. 그 모듈은 torch를 끌어오므로 상수로 두고 시험이 원문과 대조한다.
REGIONS = ("upper_left", "upper_center", "upper_right", "middle_left", "center",
           "middle_right", "lower_left", "lower_center", "lower_right")
SHA256 = re.compile(r"[0-9a-f]{64}")  # criteria_version도 이 형식: 기준 문구의 SHA-256(tools/label_criteria와 같은 값)
JUDGE = re.compile(r"[a-z0-9가-힣]{1,64}")  # 소문자 영문·숫자·완성형 한글만(NFC). 구분 기호도 없다
LOCK_WAIT_S = 5.0  # 설정 템플릿의 훅 timeout 20초보다 먼저 "busy"로 답한다


def rows(root, name):
    """체인을 검증하고 장부 줄을 돌려준다(없으면 빈 목록). 손상은 GoldError(고치거나 건너뛰지 않는다)."""
    path = os.path.join(root, name)
    problems = ledger.verify(path)
    if problems:
        raise GoldError("chain_broken", "%s %d번째 줄 %s" % (name, problems[0]["line"], problems[0]["problem"]))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle.read().removesuffix("\n").split("\n") if line]  # 장부와 같은 "\n" 나누기
    except FileNotFoundError:
        return []


def valid_issue(event, data):
    """issue()가 쓰는 발급 줄의 형식인가. 칸 집합이 정확해야 하므로 예측·점수 칸이 있으면 거짓이다."""
    if event != ISSUE_EVENT or not isinstance(data, dict) or set(data) != ISSUE_KEYS:
        return False
    zones = data["zones"]
    if not isinstance(zones, dict) or not zones or set(zones) != {"z%d" % n for n in range(1, len(zones) + 1)}:
        return False
    for zone in zones.values():
        if not isinstance(zone, dict) or set(zone) != ZONE_KEYS or not all(isinstance(v, str) for v in zone.values()) \
                or not SHA256.fullmatch(zone["image_sha256"]) or not SHA256.fullmatch(zone["crop_sha256"]) \
                or zone["region"] not in REGIONS:
            return False
    texts = (("screen_id", gold_parse.SCREEN_ID), ("nonce_sha256", SHA256), ("criteria_version", SHA256), ("judge", JUDGE))
    return len({(z["image_sha256"], z["region"]) for z in zones.values()}) == len(zones) \
        and isinstance(data["planned_repeat"], bool) \
        and all(isinstance(data[key], str) and pattern.fullmatch(data[key]) for key, pattern in texts)


def _derive(issued, raw):
    """발급 줄과 원문 바이트만으로 정해지는 기록 칸. save가 쓰고 audit가 다시 계산해 대조한다."""
    if not valid_issue(issued["event"], issued["data"]):
        raise GoldError("bad_issue_record", "발급 줄이 issue()가 쓰는 형식이 아님")
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


def repeated(records, zones, criteria_version, judge):
    """zones({zN: 구역}) 가운데 저장 기록들에서 이미 판정이 끝난 번호 이름. 발급과 저장이 같이 쓴다."""
    done = set().union(*(completed(old) for old in records))
    return sorted(name for name, z in zones.items() if (z["image_sha256"], z["region"], criteria_version, judge) in done)


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
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:  # 읽기 → 판단 → 추가를 직렬화. 프로세스가 죽으면 풀린다
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise GoldError("busy", "저장 안 함(busy): 저장 잠금을 %g초 안에 얻지 못함. 같은 붙여넣기를 다시 보낼 수 있음"
                                    % LOCK_WAIT_S)
                time.sleep(0.05)
        # 화면 ID가 없는 형식 밖 발급 줄은 어느 화면에도 속하지 않으므로 다른 화면의 저장을 막지 않는다(audit가 알린다).
        issued = [r for r in rows(root, ISSUED)
                  if isinstance(r["data"], dict) and r["data"].get("screen_id") == answer["screen_id"]]
        if len(issued) != 1:
            raise GoldError("not_issued", "발급 기록에 없는 화면")
        record = _derive(issued[0], raw)
        stored = [r["data"] for r in rows(root, STORE)]
        if any(old["nonce"] == record["nonce"] for old in stored):
            raise GoldError("nonce_reused", "이미 저장에 쓴 nonce")
        if not record["planned_repeat"]:
            again = repeated(stored, issued[0]["data"]["zones"], record["criteria_version"], record["judge"])
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
    issued = {}
    for entry in rows(root, ISSUED):
        if not valid_issue(entry["event"], entry["data"]):
            problems.append({"file": ISSUED, "seq": entry["seq"], "problem": "invalid_issue_record"})
        if isinstance(entry["data"], dict) and isinstance(entry["data"].get("screen_id"), str):
            issued[entry["data"]["screen_id"]] = entry
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
