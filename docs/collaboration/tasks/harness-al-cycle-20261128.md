# 하네스 — D7 능동 학습 선별을 회차에 잇는 준비 (2026-11-28)

```text
task_id: harness-al-cycle-20261128
owner: Claude (하위 에이전트, 구현·시험. 독립 검증·통합은 메인이 따로 수행)
status: ready_for_review (기본 꺼짐, 실제 선별·학습·평가 실행 0건)
base_sha: 0da3cb7
branch: claude/harness-al-cycle-20261128
goal: 사용자 결정 D7("재사용 중심 연결 준비, 미확정 정책 임의 구현 금지")의 지금 구현 가능한 부분 — 후보 입력 계약(D)·사람 대기열 기록(B)·
  선별 실행기와 선언(C) — 을 합성 시험으로 통과한다. 사람 정답이 필요한 사유(Q1)·보호 목록 출처(Q2)·후보 풀과 설정 값(Q3)은 비워 둔다.
설계: artifacts/harness-resume-20261127/session-6702a9/d7-proposal.md (줄 번호는 0da3cb7 기준)
changed_files: harness/al_cycle.py(신규), harness/logical_zones.py, harness/relabel.py, harness/dedupe.py(1줄), harness/supervisor.py(2줄),
  tests/test_harness_al_cycle_{inputs,queue,run}.py(신규), 이 문서
forbidden_touched: 없음(runner·sandbox·plan_gate·AGENTS.md·docs/agent·artifacts·data 미수정)
```

## 증거 구분

구현 완료 + 합성 시험 통과. **실제 실험·다음 가설 검증·실제 학습/평가·모델 누락/오탐 개선은 하지 않았고 주장하지 않는다.** 선별·대기열·선언 모두 합성 후보로만 돌렸다.
D7 요구 중 "PLAN_GATE 대기·거절을 라벨 부족 신호로 쓰지 않음"은 신호원을 승격 판정 사유 코드(`promotion_verdict.reasons`)로 잡아 지켰다(PLAN_GATE는 수정하지 않았다).

## 구현 범위

| 조각 | 함수(파일) | 하는 일 |
|---|---|---|
| D | `al_cycle.load_inputs` | `in/al/{candidates,protected,settings}.json`을 계약 inputs의 SHA로 대조해 읽는다. SHA 불일치·계약에 없음·링크·일반 파일 아님·중복 JSON 키·형식 오류·보호 목록 빔·`depends_on`이 하나가 아님은 `AlCycleError`. |
| D | `logical_zones.read_input` | 기존 `count_logical_zones`의 읽기 단계를 그대로 떼어낸 함수(동작·문구 불변, 라벨만 인자). 두 곳이 같은 규칙을 쓴다. |
| B | `al_cycle.record_queue` | `human_queue` 항목마다 Silver 저장소 체인에 `al_queued` 이벤트(키 `(image_sha, zone, criteria_version, "human")`, `task_key`, `region_id`, `group_id`, `random_part`). 점수·기대 라벨·모델 출력·결함 유형·층은 기록하지 않는다. 중복 키는 `duplicate_request`, 호출자가 준 사람 완료 키는 `already_completed`로 거절, 쓰기 전에 전체 항목을 검사한다. |
| B | `relabel.fold_requests` | `al_queued`도 `requested`로 센다(기존 분기 앞에 4줄). 재라벨 요청과 대기열이 서로의 중복을 막는다. |
| C | `al_cycle.run_select`(+`EXECUTORS`) | `load_inputs` → `active_learning.select`(scopes 없음 = 전부 사람 큐) → `out/selection.json`(`{"selected"}`만, `logical_zones` 형식)·`out/human_queue.json`. 점수·`trace`·기대 라벨은 쓰지 않는다. |
| C | `al_cycle.declare` · `need_labels` | `promotion_verdict` 줄의 사유가 `NEED_LABEL_CODES`에 드는 판정마다 `al_select` 계약(`depends_on`=그 판정 작업, seed=그 키)을 선언에 더한다. **`NEED_LABEL_CODES`·`APPROVED_INPUTS`가 하나라도 비면 읽지도 않고 그대로 돌려준다(기본 꺼짐).** |
| C | `supervisor.run` 1줄, `dedupe.PLAIN_TYPES`에 `"al_select"` | 연결 위치는 `plan_gate.gate` 다음·`register_missing` 앞(설계안). 유형 등록은 등록 경로의 고정 목록 요건. |

## 함수 수·호출 깊이 (PAIR_CODING 2.1, `tests/harness_depth_kit` 측정)

| 파일 | 함수 수 전 → 후 |
|---|---|
| `harness/al_cycle.py` | 신규 5 (`load_inputs`, `record_queue`, `run_select`, `need_labels`, `declare`) |
| `harness/logical_zones.py` | 2 → 3 |
| `harness/relabel.py` | 6 → 6 (본문만) |
| `harness/supervisor.py`·`harness/dedupe.py` | 변화 없음(5·6) |

최장 호출 경로(전이 수): `supervisor.run → al_cycle.declare → need_labels → ledger.events → ledger._load` **4**(한도, 이전 최장 4와 같고 늘리지 않음) /
`record_queue → silver_store.load → ledger.verify → ledger._check_line` 3 / `run_select → load_inputs → active_learning.check_inputs → protected_reason` 3 /
`run_select → active_learning.select → check_inputs → protected_reason` 3. runner가 부르는 executor 표는 동적 호출이라 정적 측정에 안 잡힌다(`runner.drain`은 executor 안쪽을 세지 않는 기존 한계 그대로, 위 executor 안쪽 깊이는 별도 측정).

## 비어 있는 결정 자리 (사용자 결정 전 — 구현하지 않음)

| 자리 | 코드 위치 | 상태 | 추천안(미결정) |
|---|---|---|---|
| Q1 "사람 정답 필요" 승격 사유 코드 | `al_cycle.NEED_LABEL_CODES = frozenset()` | 비어 있음 = 선언 0건 | `bootstrap_unmeasured`·`bootstrap_too_few_cards`·`false_alarm_unmeasured` 셋. 근거: 셋 다 결함·정상 구역 표본 수 부족이다. 나머지 사유(`bootstrap_lower_not_positive`·`direction_unstable`·`sensitivity_vacuous`·`abstain_*`)는 라벨을 늘려도 풀린다는 근거가 없다. |
| Q2 보호 목록(봉인·보정의 이미지 SHA·그룹 ID) 출처 | `in/al/protected.json`(계약 inputs SHA로 고정) | 출처 미정. 봉인 자료는 열지 않았다 | 봉인 시점에 남긴 기존 SHA·그룹 기록이 있으면 그것, 없으면 실제 실행 보류. D4 범위(468·C4·350·D1·D1b·11-19)와 400장 후보 그룹을 모두 포함. |
| Q3 후보 풀·설정 값(`error_priority`·`stratum_scarcity`·상한·`budget`·`threshold_width`) | `al_cycle.APPROVED_INPUTS = {}` (사용자 승인 입력 SHA) | 비어 있음 | 라벨 없는 개발 풀(보호 목록 제외)에서 Python이 후보 파일을 만들고, 설정 값은 첫 실행 전 사용자 승인 후 SHA로 고정. |
| (Q3와 함께) Silver 정책 범위 `scopes` | `run_select`가 `[]` 고정 | 선별 항목은 전부 사람 큐 | 승인된 Silver 정책이 정해지면 그 범위를 입력으로 받는다. |

## 독립 평가 400장과 능동 학습 선별의 분리

**이번에 보장하는 것(코드·시험으로 확인)**
1. 선별 후보에서 보호 목록(봉인·보정)의 이미지 SHA·그룹 ID를 제외한다(`active_learning.select` 기존 동작, `run_select` 시험이 제외를 확인).
2. 보호 목록 네 개(sealed·calibration의 image_shas·group_ids)가 하나라도 비면 `load_inputs`가 거절한다. **빈틈**: `active_learning.protected_reason`의 `all()`은 빈 목록에서 참이라 모든 후보가 통과한다. 기존 함수와 이를 쓰는 기존 시험(`OPEN` 상수가 빈 목록)은 바꾸지 않고, `tests/test_harness_al_cycle_inputs.py`가 통과 사실과 `load_inputs`의 거절을 함께 고정한다.
3. 선별 결과 파일에 점수·기대 라벨이 없다(Claude·사람 화면 앵커링 방지). 대기열 이벤트에도 없다.
4. `al_queued`에 `group_id`를 남겨, 400장 선정 쪽이 같은 체인을 읽어 대기열 그룹을 뺄 수 있다(반대 방향의 재료).

**남은 빈틈(이번 범위 밖, 여전히 열려 있음)**
- 400장 후보 그룹을 `protected.sealed`에 넣는 일: Q2 결정과 400장 후보 그룹 확정 뒤에만 가능하다. 넣지 못하면 실제 실행은 보류해야 한다. `load_inputs`는 목록이 **비어 있지 않음**만 확인하며 목록이 **완전함**은 확인할 수 없다.
- 반대 방향(능동 학습 대기열 → 400장 제외): 400장 선정 코드가 `al_queued`를 읽어 빼는 쪽은 아직 없다(트랙 A 몫). 능동 학습 결과를 독립 평가 자료에 편입하지 않는다는 규칙은 호출하는 쪽이 지켜야 한다.
- `record_queue`를 부르는 곳이 없다(대기열 기록은 함수만 있다). 호출은 `al_select` VERIFIED 뒤의 별도 연결이 필요하며 사람 화면 발급(Gold) 경로와 함께 정해야 한다.

## 한계·발견 (사용자 확인 필요)

- **runner는 `al_select`에 입력 사본(in/)을 만들지 않는다.** `runner._execute`의 `stage_inputs`와 `sandbox.run_one`의 `HARNESS_INPUT_DIR`은 실험·학습·평가 유형에만 있다. 그래서 실제 runner(sandbox) 실행에서는 `run_select`가 입력 위치를 모르고 `AlCycleError`로 닫힌 채 실패한다(시험 `test_refuses_without_input_copy_location...`이 고정). 수정하려면 runner·sandbox(신뢰 경계)를 건드리고 입력 원본 위치(Q3)를 정해야 해서 이번에 하지 않았다. 직접 호출·`runner.drain(dict)` 시험만 입력 폴더를 인자로 준다.
- `declare`는 `now` 인자를 받지 않는다(쓰지 않아 뺐다). 선언은 판정 줄에서 결정론으로 파생되고 매 회차 같은 계약을 만들며, 이미 등록된 것은 `register_missing`이 다시 등록하지 않는다.
- `al_select`는 `dedupe.PLAIN_TYPES`에 등록되어 사람이 `declared.json`에 직접 적어도 등록된다(결정론 작업, 실행은 `--executors`에 `harness.al_cycle:EXECUTORS`를 붙인 경우만). 운영 executor 표에는 붙이지 않았다.
- 승격 판정 줄에 `reasons`가 어떤 값이든 `NEED_LABEL_CODES`와 교집합이 있어야만 선언된다. 형식이 틀린 줄(`task_key` 문자열 아님·`reasons` 목록 아님)은 무시한다.
- HTML 성과 보고(`HTML_REPORTING.md`)는 만들지 않았다: 모델 성능 평가·비교 작업이 아니고 합성 시험 결과뿐이다.

## 시험

새 시험 24개(`tests/test_harness_al_cycle_inputs.py` 6, `..._queue.py` 6, `..._run.py` 12). 기존 시험은 완화·삭제하지 않았다.

결함 주입(새 보호 분기마다 한 줄씩 망가뜨려 시험이 잡는지 확인, 모두 파일 복원): 
- D: 빈 보호 목록 검사 제거·`depends_on` 하나 조건 제거·빈 후보 허용·설정 키 검사 제거·SHA 대조 제거·링크 검사 제거 → 전부 시험이 실패로 잡음. 일반 파일 검사 제거는 시험(폴더로 대체)이 `OSError` 경로로 같은 거절을 해 못 잡았다. 그 분기는 `count_logical_zones`에서 옮긴 것이며 기존 `tests/test_harness_b5_logical_zones.py`가 FIFO로 확인한다(FIFO는 해제 시 시험이 멈출 수 있어 이번 주입은 하지 않았다).
- B: `fold_requests`의 `al_queued` 인식 제거·모델 필드 검사 제거·미리 채움 검사 제거·완료 키 거절 제거·중복 키 거절 제거·결함 유형 기록·`group_id` 제거·`random_part` 형식 검사 제거·같은 호출 안 중복 처리 제거(시험 1개 추가 후) → 전부 잡음.
- C: 빈 코드 조건 제거(셋 변형)·`depends_on` 제거·사유 교집합 조건 제거·유형·outputs 검사 제거·보호 목록 무력화·`selection.json`에 `trace` 추가·supervisor 연결 제거·`PLAIN_TYPES` 등록 제거·입력 위치 검사 제거 → 전부 잡음.

기존 합성 시험 확인: VS3(`test_harness_vs3_{entry,fixes,gate,gate_flow,doc_commit}`)·B5-11(`test_harness_b5_e2e_synthetic`)·dedupe·graph·supervisor 계약·B5 예산 깊이·복구·Silver 재라벨·논리 구역 시험 61개가 그대로 통과(개발 중 관련 시험).

전체 하네스 시험: FULL_SUITE_PLACEHOLDER

## 롤백

브랜치 `claude/harness-al-cycle-20261128`(base 0da3cb7)는 main에 통합하지 않았다. 되돌리려면 이 브랜치를 버리면 된다. 부분 롤백은 커밋 단위: C(supervisor 1줄·`dedupe` 1줄 포함) → B → D 순서의 역순으로 `git revert`. `al_cycle.py`를 지우면 `supervisor.py`의 `al_cycle.declare` 줄과 `dedupe.PLAIN_TYPES`의 `"al_select"`도 함께 되돌려야 한다. 이미 쓰인 `al_queued` 장부 줄은 없다(실제 실행 0건).

## 미검증

실제 runner(sandbox) 안에서의 `al_select` 실행, 실제 후보 풀·보호 목록(봉인 SHA·그룹)의 완전성, Q1 코드가 켜진 상태의 실제 승격 판정 흐름, 사람 화면·Gold 연결, 400장 후보 그룹의 보호 목록 반영.
