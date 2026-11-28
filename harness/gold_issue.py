"""Gold 화면 발급(DESIGN 5-2의 1). 화면 ID와 일회용 nonce를 만들고, 발급 기록을 남긴 뒤에만 화면 메타데이터를 돌려준다.

발급 장부(root/gold/issued.jsonl, 1단계 해시 체인)에는 nonce의 sha256만 둔다. nonce 원문은 돌려주는 메타데이터(화면)에만
있다. 같은 사용자 권한의 에이전트는 화면을 읽거나 스스로 발급할 수 있으므로 이것이 위조를 막지는 못한다(gold_store 참고).
화면 데이터에는 예측 칸이 없다. 구역 정보는 gold_store.ZONE_KEYS 세 칸만 받으며 점수·예측 같은 다른 칸은 거절한다.
HTML 생성은 이 모듈의 범위가 아니다. 화면을 만드는 쪽은 "직접판정" 확인 칸을 꺼진 상태로 두고, 사람이 켰을 때만
`# 직접판정=확인` 줄을 써야 한다.
완료 키의 칸은 gold_store의 좁은 형식만 받는다: region은 정본 구역 이름, criteria_version은 기준 문구의 SHA-256(소문자 hex),
judge는 NFC로 맞춘 뒤 소문자 영문·숫자·완성형 한글. 결함 종류가 다른 기준은 기준 문구가 달라야 한다(같은 SHA를 쓰면
같은 사진·구역이 완료 키로 겹친다). 기준 문구를 한 글자라도 바꾸면 새 판본이다.
이미 끝난 키가 있으면 planned_repeat가 아닌 한 발급하지 않는다(사람이 판정한 뒤 거절되지 않게). 이 확인은 잠금 없이 하므로
최종 거절은 save가 한다. 끝나기 전에 같은 키를 두 번 발급하는 것은 막지 않는다(나중 화면은 저장 때 거절된다).
"""
import hashlib
import os
import secrets
import unicodedata

from . import gold_parse, gold_store, ledger


def issue(root, zones, criteria_version, judge, now, planned_repeat=False):
    """zones(보여 줄 순서)에 z1..zN을 붙여 발급한다. planned_repeat는 계획된 자기 일치도 재판정 표시이며 발급 때만 정한다."""
    if not isinstance(zones, list):
        raise ValueError("구역 목록이 아님")
    if isinstance(judge, str):
        judge = unicodedata.normalize("NFC", judge)
    screen_id, nonce = secrets.token_hex(8), secrets.token_hex(16)
    screen = {"screen_id": screen_id,
              "zones": {"z%d" % n: dict(z) if isinstance(z, dict) else z for n, z in enumerate(zones, 1)},
              "criteria_version": criteria_version, "judge": judge, "planned_repeat": planned_repeat}
    data = dict(screen, nonce_sha256=hashlib.sha256(nonce.encode("ascii")).hexdigest())
    if not gold_store.valid_issue(gold_store.ISSUE_EVENT, data):
        raise ValueError("발급 형식 오류: 구역은 image_sha256·region·crop_sha256만(예측 칸 금지, 중복 금지, 정본 구역 이름), "
                         "criteria_version은 소문자 SHA-256, judge는 소문자 영문·숫자·한글, planned_repeat는 bool")
    if not planned_repeat:
        stored = [r["data"] for r in gold_store.rows(root, gold_store.STORE)]
        again = gold_store.repeated(stored, screen["zones"], criteria_version, judge)
        if again:
            raise gold_parse.GoldError("completed_key", "이미 끝난 판정: %s(화면을 발급하지 않음)" % ", ".join(again))
    # 기록이 먼저다. 쓰지 못하면 예외가 나가고 nonce는 호출자에게 전달되지 않는다.
    ledger.append(os.path.join(root, gold_store.ISSUED), now, gold_store.ISSUE_EVENT, data)
    return dict(screen, nonce=nonce, confirm={"key": gold_parse.CONFIRM_KEY, "required_value": gold_parse.CONFIRM_VALUE,
                                              "preset": False})
