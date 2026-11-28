"""B5-5: 비전 예산(budget의 vision_zone)에 차감할 '논리 구역 수'를 하네스가 센다(2026-11-28 사용자 조건부 승인, 나안).

- 이 값은 **실제 AI 사용량(호출·토큰·본 사진 수)이 아니다**. 계약 입력으로 선언한 후보 목록에 적힌 구역의 수다. Claude가 같은 구역을 여러 번
  보거나, 목록에 없는 입력 사진을 읽거나, 같은 task_key를 재개·다시 실행해도 이 값과 예산 차감은 늘지 않는다.
- 등록자가 적은 숫자는 쓰지 않는다. 작업 폴더의 입력 사본 in/<INPUT>을 한 번 읽고, **읽은 바이트**의 sha256이 계약 inputs와 같을 때만 그 바이트를 센다
  (대조와 해석 사이 틈 없음). 목록이 바뀌면 SHA → task_key가 달라지고, 같은 task_key로 바뀐 사본은 여기서 거절한다.
- 형식: {"selected": [...]} 하나뿐이다. 항목은 active_learning.select의 selected 항목과 정확히 같다(KEEP + part + random_part).
  select의 반환 전체는 받지 않는다: 이 파일은 Claude가 읽는 입력인데 trace에는 선별 점수가, silver_queue·human_queue 소속에는 기대 라벨이
  드러나고(앵커링), 세지 않는 목록에 구역을 더 넣을 수 있다. 모르는 키·중복 JSON 키(뒤 값만 세어지지만 파일에는 앞 목록도 남는다)도 거절한다.
- 중복: region_id가 같거나 (image_sha, zone)이 같으면(앞뒤 공백·대소문자 무시, 라벨 단위는 relabel·silver_gate와 같다) 거절한다. 빈 목록도 거절.
- 한도 비교·차감·멱등은 budget.charge가 한다(여기서 다시 하지 않는다). 호출자 claude_job.execute(VS4):
  budget.charge(root, "vision_zone", count_logical_zones(task_dir, contract), now, key=task_key) — Claude 실행 시작 직전, key는 run_token이 아니다.
  LogicalZoneError면 그 작업만 거절한다(fail-closed).
호출 깊이: count_logical_zones → read_input 1(_unique_keys는 json 콜백). 나머지는 표준 라이브러리다.
"""
import hashlib
import json
import os
import stat

from .active_learning import KEEP

INPUT = "candidates/selection.json"  # 계약 inputs의 고정 상대 경로(B5-7의 silver/labels.json과 같은 방식)
ITEM_KEYS = frozenset(KEEP) | {"part", "random_part"}


class LogicalZoneError(ValueError):
    pass


def _unique_keys(pairs):
    found = dict(pairs)
    if len(found) != len(pairs):
        raise LogicalZoneError("JSON 객체에 같은 키가 두 번 있다")
    return found


def read_input(task_dir, contract, rel, label="후보 목록"):
    """task_dir/in/<rel>의 읽은 바이트를 계약 inputs의 SHA와 대조한 뒤 JSON(중복 키 거절)으로 해석해 돌려준다. 어긋나면 LogicalZoneError.
    al_cycle.load_inputs도 같은 읽기를 쓴다(링크·일반 파일·SHA·중복 키 규칙을 한 곳에 둔다)."""
    want = contract.get("inputs", {}).get(rel)
    if not isinstance(want, str):
        raise LogicalZoneError("계약 inputs에 %s(%s)이 없다" % (label, rel))
    path = task_dir
    for part in ["in"] + rel.split("/"):  # 원본·다른 파일을 가리키는 링크 사본은 읽지 않는다
        path = os.path.join(path, part)
        if os.path.islink(path):
            raise LogicalZoneError("%s 사본 경로에 링크가 있다: %s" % (label, path))
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):  # FIFO는 여는 순간 멈춘다
            raise LogicalZoneError("%s 사본이 일반 파일이 아니다" % label)
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise LogicalZoneError("%s 사본을 읽을 수 없다: %s" % (label, exc))
    if hashlib.sha256(data).hexdigest() != want.lower():
        raise LogicalZoneError("%s 사본의 SHA가 계약과 다르다" % label)
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError) as exc:  # LogicalZoneError도 ValueError: 사유를 그대로 담는다
        raise LogicalZoneError("%s 해석 실패: %s" % (label, exc))


def count_logical_zones(task_dir, contract):
    """task_dir/in/INPUT(SHA 확인)의 후보 구역 수(1 이상). 셀 수 없으면 LogicalZoneError."""
    body = read_input(task_dir, contract, INPUT)
    items = body.get("selected") if isinstance(body, dict) and set(body) == {"selected"} else None
    if not isinstance(items, list) or not items:
        raise LogicalZoneError('후보 목록은 비어 있지 않은 {"selected": [...]} 하나여야 한다')
    ids, zones = set(), set()
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_KEYS \
                or not all(isinstance(item[k], str) and item[k].strip() for k in KEEP) \
                or item["part"] not in ("ranked", "random") or item["random_part"] is not (item["part"] == "random"):
            raise LogicalZoneError("후보 항목 형식이 select의 selected 항목과 다르다: %s" % repr(item)[:200])
        rid = item["region_id"].strip().casefold()
        zone = (item["image_sha"].strip().casefold(), item["zone"].strip().casefold())
        if rid in ids or zone in zones:
            raise LogicalZoneError("중복 구역: region_id=%r image_sha·zone=%r" % (item["region_id"], zone))
        ids.add(rid)
        zones.add(zone)
    return len(zones)
