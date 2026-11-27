"""`claude -p --output-format stream-json` 출력(줄 단위 JSON) 해석: 세션 ID, init의 모델, 결과, 한도 이벤트.

실제 출력 형태는 이 설치본에서 확인하지 않았다(EVIDENCE 7절 1번). 그래서 아래 규칙은 추정을 줄이는 쪽으로 정했다.
- 한도 이벤트: `"type": "rate_limit_event"`인 줄. 필드(resetsAt·resetsAtSeconds·status·rateLimitType)는 이벤트 최상위나
  한 단계 아래 dict(예: rate_limit_info)에서 찾는다.
- 재개 시각: epoch 초, epoch 밀리초(1e11 초과), 숫자 문자열, 시간대가 있는 ISO 8601 문자열만 받는다. 시간대 없는 ISO·
  2001년 이전 값(상대 초일 수 있음)·bool·그 밖은 None(추정 금지). resetsAtSeconds도 같은 규칙(상대 초로 해석하지 않는다).
- 한도에 걸렸는가: status가 LIMIT_STATUSES이거나, 이벤트가 있고 status가 ALLOWED_STATUSES가 아니며 실행이 성공하지 않았을 때.
  (status가 허용이면 성공·실패와 무관하게 한도가 아니다: 실패는 일반 실패로 다룬다.)
- 단기/주간: rateLimitType(또는 type 이름 필드) 값으로만 나눈다. 모르는 값·없음은 "unknown"(단기로 두지 않는다).
"""
import datetime
import json

LIMIT_STATUSES = ("rejected",)
ALLOWED_STATUSES = ("allowed", "allowed_warning")
SHORT_TYPES = ("five_hour",)
WEEKLY_TYPES = ("seven_day", "seven_day_opus", "seven_day_sonnet")
_MIN_EPOCH = 1e9  # 2001-09-09. 이보다 작은 값은 상대 초일 수 있어 해석하지 않는다
_MS_EPOCH = 1e11  # 이보다 크면 밀리초로 본다(초라면 서기 5138년)


def parse_reset(value):
    """재개 시각 → epoch 초(float) 또는 None(해석 불가)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().replace(".", "", 1).isdigit():
        value = float(value.strip())
    if isinstance(value, (int, float)):
        value = value / 1000.0 if value > _MS_EPOCH else float(value)
        return float(value) if _MIN_EPOCH <= value < _MS_EPOCH else None  # NaN·무한대도 여기서 거절된다
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.timestamp() if parsed.tzinfo is not None else None


def _lookup(event, names):
    """event 최상위, 없으면 한 단계 아래 dict에서 names 중 처음 찾은 값. 없으면 None."""
    for name in names:
        if name in event:
            return event[name]
    for inner in event.values():
        if isinstance(inner, dict):
            for name in names:
                if name in inner:
                    return inner[name]
    return None


def classify_kind(value):
    """"short" | "weekly" | "unknown"."""
    if value in SHORT_TYPES:
        return "short"
    if value in WEEKLY_TYPES:
        return "weekly"
    return "unknown"


def scan(lines, returncode):
    """출력 줄 → 요약 dict. 해석 못 한 줄은 bad_lines로 센다(무시하지 않고 기록)."""
    found = {"session_id": None, "init": None, "result": None, "rate_limit": None, "events": 0, "bad_lines": 0}
    for raw in lines:
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            found["bad_lines"] += 1
            continue
        if not isinstance(event, dict):
            found["bad_lines"] += 1
            continue
        found["events"] += 1
        if found["session_id"] is None and isinstance(event.get("session_id"), str):
            found["session_id"] = event["session_id"]
        if event.get("type") == "system" and event.get("subtype") == "init" and found["init"] is None:
            found["init"] = {"model": event.get("model") if isinstance(event.get("model"), str) else None,
                             "effort": _lookup(event, ("effort", "effortLevel", "effort_level"))}
        elif event.get("type") == "result":
            found["result"] = event
        elif event.get("type") == "rate_limit_event":
            raw_reset = _lookup(event, ("resetsAt", "resetsAtSeconds"))
            found["rate_limit"] = {"resets_at": parse_reset(raw_reset), "resets_at_raw": raw_reset,
                                   "status": _lookup(event, ("status",)),
                                   "type_raw": _lookup(event, ("rateLimitType", "rate_limit_type")),
                                   "kind": classify_kind(_lookup(event, ("rateLimitType", "rate_limit_type")))}
    result = found["result"]
    found["success"] = returncode == 0 and isinstance(result, dict) and result.get("is_error") is not True
    limit = found["rate_limit"]
    found["limited"] = limit is not None and (limit["status"] in LIMIT_STATUSES or (
        limit["status"] not in ALLOWED_STATUSES and not found["success"]))
    return found
