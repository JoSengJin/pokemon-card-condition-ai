"""Gold 화면 발급(DESIGN 5-2의 1). 화면 ID와 일회용 nonce를 만들고, 발급 기록을 남긴 뒤에만 화면 메타데이터를 돌려준다.

발급 장부(root/gold/issued.jsonl, 1단계 해시 체인)에는 nonce의 sha256만 둔다. nonce 원문은 돌려주는 메타데이터(화면)에만
있다. 같은 사용자 권한의 에이전트는 화면을 읽거나 스스로 발급할 수 있으므로 이것이 위조를 막지는 못한다(gold_store 참고).
화면 데이터에는 예측 칸이 없다. 구역 정보는 아래 ZONE_KEYS 세 칸만 받으며 점수·예측 같은 다른 칸은 거절한다.
HTML 생성은 이 모듈의 범위가 아니다. 화면을 만드는 쪽은 "직접판정" 확인 칸을 꺼진 상태로 두고, 사람이 켰을 때만
`# 직접판정=확인` 줄을 써야 한다.
criteria_version은 결함 종류별 기준을 구분하는 값이어야 한다(예: 기준 문구 SHA). 종류가 다른 기준에 같은 값을 쓰면
같은 사진·구역이 완료 키로 겹친다. judge 이름은 정규화하지 않는다.
"""
import hashlib
import os
import re
import secrets

from . import gold_parse, gold_store, ledger

ZONE_KEYS = {"image_sha256", "region", "crop_sha256"}  # crop_sha256: 그때 보여 준 사진 조각(label-provenance)
SHA256 = re.compile(r"[0-9a-f]{64}")
REGION = re.compile(r"[A-Za-z0-9_.-]{1,64}")
CRITERIA = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
JUDGE = re.compile(r"\S{1,64}")


def issue(root, zones, criteria_version, judge, now, planned_repeat=False):
    """zones(보여 줄 순서)에 z1..zN을 붙여 발급한다. planned_repeat는 계획된 자기 일치도 재판정 표시이며 발급 때만 정한다."""
    if not isinstance(zones, list) or not zones:
        raise ValueError("구역 목록이 비었음")
    for zone in zones:
        if not isinstance(zone, dict) or set(zone) != ZONE_KEYS or not all(isinstance(v, str) for v in zone.values()) \
                or not SHA256.fullmatch(zone["image_sha256"]) or not SHA256.fullmatch(zone["crop_sha256"]) \
                or not REGION.fullmatch(zone["region"]):
            raise ValueError("구역은 image_sha256·region·crop_sha256만 가진다(예측 칸 금지)")
    if len({(z["image_sha256"], z["region"]) for z in zones}) != len(zones):
        raise ValueError("한 화면에 같은 (이미지, 구역)이 두 번 있음")
    if not isinstance(criteria_version, str) or not CRITERIA.fullmatch(criteria_version) \
            or not isinstance(judge, str) or not JUDGE.fullmatch(judge) or not isinstance(planned_repeat, bool):
        raise ValueError("criteria_version·judge·planned_repeat 형식 오류")
    screen_id, nonce = secrets.token_hex(8), secrets.token_hex(16)
    screen = {"screen_id": screen_id, "zones": {"z%d" % n: dict(z) for n, z in enumerate(zones, 1)},
              "criteria_version": criteria_version, "judge": judge, "planned_repeat": planned_repeat}
    # 기록이 먼저다. 쓰지 못하면 예외가 나가고 nonce는 호출자에게 전달되지 않는다.
    ledger.append(os.path.join(root, gold_store.ISSUED), now, "gold_screen_issued",
                  dict(screen, nonce_sha256=hashlib.sha256(nonce.encode("ascii")).hexdigest()))
    return dict(screen, nonce=nonce, confirm={"key": gold_parse.CONFIRM_KEY, "required_value": gold_parse.CONFIRM_VALUE,
                                              "preset": False})
