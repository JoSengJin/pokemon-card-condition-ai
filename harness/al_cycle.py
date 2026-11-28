"""D7: 능동 학습 선별(active_learning)을 하네스 회차에 잇는 준비 코드(2026-11-28 사용자 결정 D7, 설계 artifacts/harness-resume-20261127/session-6702a9/d7-proposal.md).
**기본 꺼짐**: 허용 사유 코드(NEED_LABEL_CODES)와 승인된 입력 SHA(APPROVED_INPUTS)가 비어 있어 declare는 아무것도 선언하지 않는다. 실제 선별·학습·평가는 하지 않는다.

- D load_inputs: 작업 폴더 in/al/{candidates,protected,settings}.json을 계약 inputs의 SHA로 대조해 읽는다(읽기·링크·중복 키 규칙은 logical_zones.read_input,
  형식은 active_learning.check_inputs). 보호 목록(sealed·calibration의 image_shas·group_ids) 네 개가 하나라도 비면 거절한다: active_learning.protected_reason은
  빈 목록도 통과시킨다(all()이 빈 목록에서 참). 기존 함수는 바꾸지 않고 여기서 막는다. seed = 계약 depends_on의 단 하나(승격 판정 작업 키).
- B record_queue: 사람 대기열 항목을 Silver 저장소 체인에 `al_queued`로 남긴다. 점수·기대 라벨·모델 출력·결함 유형·층은 넣지 않는다(사람 판정 화면 비노출,
  group_id는 남긴다: 독립 평가 자료 선정에서 반대 방향 제외에 쓸 수 있게). relabel.fold_requests가 이 이벤트도 요청으로 센다.
- C run_select(executor 표 EXECUTORS) · declare: 선별 결과 out/selection.json({"selected"}만, logical_zones 형식)·out/human_queue.json. declare는 승격 판정 줄 중
  NEED_LABEL_CODES 사유를 가진 판정마다 al_select 계약을 더한다(필수 입력 APPROVED_INPUTS가 비면 아무 일도 하지 않는다).
- 미정(사용자 결정 전, 구현하지 않고 빈 상수로 둠): Q1 어떤 사유가 "사람 정답 필요"인가, Q2 보호 목록 출처, Q3 후보 풀·설정 값.
- 한계: runner는 실험·학습·평가 유형만 입력 사본(in/)을 만들고 HARNESS_INPUT_DIR을 넘긴다. al_select 유형은 아직 그렇지 않아 실제 runner 실행에서는
  입력 사본이 없어 fail-closed로 실패한다(Q3와 함께 정한다). run_select를 직접 호출하는 시험만 입력 폴더를 인자로 준다.
호출 깊이: declare → need_labels → ledger.events → _load 3(supervisor.run 기준 +1 = 4). load_inputs → logical_zones.read_input 1, → active_learning.check_inputs → protected_reason 2.
"""
import json
import os

from . import contract as ct
from . import active_learning, logical_zones, relabel, silver_policy, silver_store
from .active_learning import ActiveLearningError

TASK_TYPE = "al_select"  # dedupe.PLAIN_TYPES에 같은 이름으로 등록한다(시험이 일치를 확인)
CANDIDATES, PROTECTED, SETTINGS = "al/candidates.json", "al/protected.json", "al/settings.json"
OUTPUTS = ["selection.json", "human_queue.json"]
NEED_LABEL_CODES = frozenset()  # Q1: 비어 있음 = 선언 0건. 추천안(미결정): bootstrap_unmeasured·bootstrap_too_few_cards·false_alarm_unmeasured
APPROVED_INPUTS = {}  # Q2·Q3: 사용자가 승인한 {입력 경로: SHA-256}. 비어 있으면 declare는 아무것도 하지 않는다


class AlCycleError(ValueError):
    pass


def load_inputs(task_dir, contract):
    """task_dir/in/al/*.json을 읽어 {candidates, protected, config, budget, seed}를 돌려준다. 어긋나면 AlCycleError(아무것도 추정하지 않는다)."""
    try:
        cands, prot, sett = (logical_zones.read_input(task_dir, contract, rel, "능동 학습 입력") for rel in (CANDIDATES, PROTECTED, SETTINGS))
        deps = contract.get("depends_on")
        if not (isinstance(deps, list) and len(deps) == 1 and isinstance(deps[0], str)):
            raise AlCycleError("depends_on은 승격 판정 작업 하나여야 한다(seed로 쓴다)")
        if not isinstance(cands, list) or not cands or not isinstance(sett, dict) or set(sett) != {"budget", "config"}:
            raise AlCycleError("후보는 비어 있지 않은 목록, 설정은 {budget, config} 하나여야 한다")
        active_learning.check_inputs(cands, prot, sett["config"], sett["budget"], deps[0])
        if any(not prot[name][field] for name in ("sealed", "calibration") for field in ("image_shas", "group_ids")):
            raise AlCycleError("보호 목록(sealed·calibration의 image_shas·group_ids)이 비어 있으면 제외할 수 없다")
    except (ValueError, ActiveLearningError, TypeError, AttributeError, KeyError) as exc:  # ValueError: LogicalZoneError·AlCycleError 포함
        raise AlCycleError("%s: %s" % (type(exc).__name__, exc))
    return {"candidates": cands, "protected": prot, "config": sett["config"], "budget": sett["budget"], "seed": deps[0]}


def record_queue(root, now, task_key, result, criteria_version, completed=()):
    """select 결과의 human_queue 항목마다 al_queued 이벤트를 Silver 저장소에 남긴다. 반환 {ok, accepted, rejected}(request_relabel과 같은 모양).

    키 = (이미지 SHA, 구역, 기준 판본, "human"). 이미 요청·대기열에 있으면 duplicate_request, completed(사람 Gold가 끝낸 키 목록)에 있으면 already_completed로 거절한다.
    모델 결과·미리 채운 필드가 있는 항목과 형식 오류는 아무것도 쓰기 전에 거절한다(AlCycleError·RelabelError·PolicyError). silver_queue는 기록하지 않는다.
    """
    items = result.get("human_queue") if isinstance(result, dict) else None
    if not isinstance(items, list) or not isinstance(criteria_version, str) or not criteria_version:
        raise AlCycleError("result는 human_queue 목록을, criteria_version은 비어 있지 않은 문자열을 가져야 한다")
    ct.check_key(task_key)
    relabel.reject_model_fields(items)
    silver_policy.reject_prefilled(items)
    rows = []
    for item in items:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in ("region_id", "group_id")) \
                or not isinstance(item.get("random_part"), bool):
            raise AlCycleError("대기열 항목에는 region_id·group_id(문자열)와 random_part(bool)가 필요하다: %r" % (item,))
        key = relabel.key_of(dict(item, criteria_version=criteria_version, judge="human"))
        rows.append({"key": list(key), "task_key": task_key, "region_id": item["region_id"], "group_id": item["group_id"],
                     "random_part": item["random_part"]})
    finished, accepted, rejected = {tuple(k) for k in completed}, [], []
    with silver_store.lock(root):
        seen = relabel.fold_requests(silver_store.load(root))["requested"]
        for row in rows:
            key = tuple(row["key"])
            if key in seen or key in finished:
                rejected.append({"key": row["key"], "reason": "duplicate_request" if key in seen else "already_completed"})
            else:
                silver_store.append(root, now, "al_queued", row)
                seen.add(key)
                accepted.append(row["key"])
    return {"ok": True, "accepted": accepted, "rejected": rejected}
