"""붙여넣은 Gold 답과 "중단" 명령의 구분·파싱(DESIGN 5-2·13절). 추정·보정하지 않고, 어긋나면 GoldError(코드, 설명).

형식(기존 `# 화면=`·`# 제출시각=`·`zN=값`에 nonce와 직접 판정 확인 줄을 더한 것):
    # 화면=<16자 hex>
    # nonce=<32자 hex>
    # 직접판정=확인
    # 제출시각=2026-12-01T10:00:00+09:00
    z1=정상|결함|불가|미확인
빈 줄과 줄 앞뒤 공백만 무시한다. 그 밖의 줄(붙여넣기 앞뒤의 설명 글 포함)은 거절한다.
"""
import re
from datetime import datetime

VALUES = ("정상", "결함", "불가", "미확인")  # 정본: tools/self_agreement/answers.VALUES(시험이 대조한다)
UNJUDGED = "미확인"  # 판정하지 않음. 완료 라벨이 아니다("불가"는 보고 내린 판정이라 완료다)
STOP = "중단"
CONFIRM_KEY, CONFIRM_VALUE = "직접판정", "확인"
HEADERS = ("화면", "nonce", CONFIRM_KEY, "제출시각")
MAX_BYTES = 64 * 1024
SCREEN_ID = re.compile(r"[0-9a-f]{16}")
NONCE = re.compile(r"[0-9a-f]{32}")
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}")
# 이런 줄이 하나라도 있으면 Gold 붙여넣기 시도로 본다(머리 줄을 빠뜨린 붙여넣기가 말없이 지나가지 않게).
MARKER = re.compile(r"\s*(#\s*(화면|nonce|직접판정)\s*=|z[0-9]+\s*=)")


class GoldError(ValueError):
    """args = (거절 코드, 설명). 설명에는 붙여넣은 원문을 옮기지 않는다(줄 번호·번호 이름만)."""


def classify(prompt):
    """"stop" | "gold" | None. 중단은 앞뒤 공백을 뺀 전체가 정확히 "중단"일 때만이다(문장 속 단어는 명령이 아니다)."""
    if prompt.strip() == STOP:
        return "stop"
    return "gold" if any(MARKER.match(line) for line in prompt.splitlines()) else None


def parse(prompt):
    """{"screen_id", "nonce", "confirm", "submitted_at", "answers": {zN: 값}}."""
    try:
        size = len(prompt.encode("utf-8"))
    except UnicodeEncodeError:
        raise GoldError("not_utf8", "UTF-8로 바꿀 수 없는 문자")
    if size > MAX_BYTES:
        raise GoldError("too_large", "%d바이트 초과" % MAX_BYTES)
    head, answers = {}, {}
    for number, raw in enumerate(prompt.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        is_head = line.startswith("#")
        name, equal, value = (line[1:] if is_head else line).partition("=")
        name, value = name.strip(), value.strip()
        if is_head:
            if not equal or name not in HEADERS:
                raise GoldError("unknown_line", "%d번째 줄" % number)
            if name in head:
                raise GoldError("duplicate_key", "# %s" % name)
            head[name] = value
            continue
        if not equal or not re.fullmatch(r"z[1-9][0-9]*", name):
            raise GoldError("unknown_line", "%d번째 줄" % number)
        if name in answers:
            raise GoldError("duplicate_key", name)
        if value not in VALUES:
            raise GoldError("unknown_value", name)
        answers[name] = value
    if head.get(CONFIRM_KEY) != CONFIRM_VALUE:
        raise GoldError("no_direct_judgment", '"# %s=%s" 줄이 필요함' % (CONFIRM_KEY, CONFIRM_VALUE))
    lost = [name for name in HEADERS if not head.get(name)]
    if lost:
        raise GoldError("missing_line", ", ".join("# " + name for name in lost))
    if not SCREEN_ID.fullmatch(head["화면"]):
        raise GoldError("bad_screen_id", "16자 hex가 아님")
    if not NONCE.fullmatch(head["nonce"]):
        raise GoldError("bad_nonce_format", "32자 hex가 아님")
    try:
        if not STAMP.fullmatch(head["제출시각"]):
            raise ValueError
        datetime.fromisoformat(head["제출시각"])
    except ValueError:
        raise GoldError("bad_submitted_at", "시간대(+09:00 꼴)가 있는 시각이 아님")
    if not answers:
        raise GoldError("missing_line", "zN 답 줄 없음")
    return {"screen_id": head["화면"], "nonce": head["nonce"], "confirm": head[CONFIRM_KEY],
            "submitted_at": head["제출시각"], "answers": answers}
