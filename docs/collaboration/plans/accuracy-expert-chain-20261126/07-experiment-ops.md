# 07. MLOps·실험 운영 — 기록 파이프라인 대조표, 최소 변경 설계, 구현 task 계약 (2026-11-26, Claude)

범위: 읽기 전용 조사, 저장된 답 파일의 python 재집계, 이 문서 작성만 했다. 구현·학습·추론·라벨 수정·외부 AI 호출·`./develop`·`./experiment`·`./review`·commit은 하지 않았다. 다른 파일은 고치지 않았다.

**결론 3줄**
1. **01~06이 요구한 기록 7개 중 실행기(`./experiment`)에 들어 있는 것은 0개다.** 실행기는 0.5 문턱의 FP/FN·새 오답·사람점·분모 0 표시만 기록한다(`experiment_record.py:153`, `regression_audit.py:17`, `acceptance_caps.py:19-23`). 판단 불가·제외 건수·판정 주체·촬영 층·보류·문턱 근처·분기 규칙은 모두 행 변환 단계에서 사라지거나(변환기), 실행기 밖의 일회성 스크립트에만 있다.
2. **정보가 사라지는 곳은 두 군데로 좁혀진다.** ① 답 가져오기·행 변환이 `정상|결함` 외의 상태를 조용히 버린다(`d2_rows.py:36`, `mobile_corner_label_import.py:25`). ② 실행기 행 형식이 `id·target·box…`만 정체성으로 본다(`cross_review_evidence.py:54`). 02가 미확인으로 남긴 "D2 엣지가 상자 미확인 24구역을 포함한 이유"는 코드 한 줄이다: `d2_rows.py:68`의 `need_ok=False`.
3. **실행기 본체는 이미 구조 제한을 넘는다**(함수 17개 > 7, 호출 깊이 5 > 4). 그래서 새 기록은 `acceptance_caps.py`와 같은 방식으로 **새 파일 + 기존 함수 안의 호출 1줄**로만 넣는다. 사이드카 파일을 행 밖에 두면 평가 자료 해시(`cohort_sha256`)와 과거 판정이 바뀌지 않는다.

## 1. 이 분야에서 실제로 한 일

읽은 원문(전체): `00-BRIEF.md`, `01`~`06`(04 부록 포함), `AGENTS.md`(주입 전문), `docs/AGENT_START.md`, `COMMON_EXPERIMENT_RECORDS.md`(156줄), `PAIR_CODING.md`(151줄), `docs/agent/QUALITY_RULES.md` 21~65·93~142줄.

읽은 코드(전체): `experiment`(셸 5줄), `card_condition/experiment_record.py`(350줄), `card_condition/acceptance_caps.py`, `card_condition/regression_audit.py:5-36`(`compare_predictions`), `card_condition/cross_review_evidence.py:33-56`(`experiment`), `card_condition/region_dataset.py:1-60`, `card_condition/evaluation_suite_metrics.py`, `tools/d2_rows.py`, `tools/mobile_corner_label_import.py`, `tools/mobile_surface_label_import.py`, `tools/label_criteria.py`, `tools/self_agreement/import_round.py`, `tools/self_agreement/decide.py`, `tools/self_agreement/stats.py`, `tools/diagnostics/corner-chance-check-20261124/check.py:86-103`.
부분 확인(grep): `tools/self_agreement/plan.py:1-40`, `tools/mobile_corner_label_pages.py:23`, `tools/diagnostics/corner-size-threshold-20261123/measure.py:1-30`, `tools/experiments/corner-same-photo-pair-cv-20261102/worker.py:1-60`, `tests/test_acceptance_caps.py:1-40`, 실험 폴더 2개(`20261121T050740-8588eeb0`, `20261103T131123-7fa5d398`)의 plan/result/observations 키.

집계(모두 `python3 -I`, 입력 변경 없음, 결과는 stdout과 이 문서뿐):
- **O1 파일별 함수 수**: `grep -cE '^\s*(async )?def '`. 결과는 4-0절 표.
- **O2 D1 답 재집계**: `artifacts/d1-labels-20261103/{cor,edge-zone}-answers.txt`의 (상자 확인 × 상태). 모서리는 확인 상자에서 정상 330·결함 178·미확인 16, 미확인 상자에서 미확인 20·정상 3·결함 5다. 엣지는 확인 상자에서 정상 646·결함 272·미확인 2, 미확인 상자에서 정상 14·결함 10이다. 02의 508행·44제외와 942행이 같다.
- **O3 B2 불일치 원인**: `cohort2-retest-20261125/responses/{A2,B2}.txt`를 `ai-responses/screen-*-AI-{pass1,final}-20261125.txt`와 zN 값으로 대조했다. A2는 pass1 56/64·final 64/64, B2는 pass1 50/64·final 64/64다. **02가 남긴 "B2 50/64 대 64/64" 차이는 대조한 AI 파일(pass1/final)이 달랐기 때문이다.**

안 한 것: 엣지 화면 가져오기 도구 탐색(엣지는 `d2_rows`가 원 답을 직접 읽는다. 다른 엣지 import는 grep 0건), 개발 946행 `rows.json`을 만든 스크립트 특정(plan `input_sha256`에 파일 해시만 있다, 생성 코드 미확인), 실제 단위 시험 실행(구현 금지라 시험이 아직 없다).

## 2. 발견 — 기록 항목 대조표 (있음/없음, 코드 인용)

### 2-1. 대조표

| # | 요구 항목(출처) | 지금 있는가 | 근거(파일:줄) | 빠지는 지점 |
|---|---|---|---|---|
| R1 | 판단 불가 보존(01 G1, 02 2-2) | **없음** | 화면 상태는 `미확인→정상→결함` 셋(`mobile_corner_label_pages.py:23`). 가져오기는 그 밖의 상태가 있으면 줄 전체를 거절하고(`mobile_corner_label_import.py:23`, 표면 `mobile_surface_label_import.py:22`) 미확인은 키를 빼서 `None`으로 남긴다(`:25`, 표면 `:24`). `region_rows`는 값이 전부 None인 칸을 건너뛴다(`region_dataset.py:21-22`) | 화면·가져오기·행 변환 세 단계 |
| R2 | 변환 시 빠진 건수(02 L3, 05 4-1) | **없음**(실행기). 옛 경로에만 부분 | `d2_rows.zone_rows` docstring은 "counts in the summary"라고 하지만(`d2_rows.py:27`) 정규식이 `정상|결함`만 잡고(`:36`) 요약은 행 수·그룹·양성뿐이다(`:72-73`). 엣지만 `need_ok=False`(`:68`). 옛 평가 묶음은 `unknown_truth_units`를 센다(`evaluation_suite_metrics.py:71-72`)·`region_audit`도 None을 센다(`region_dataset.py:37-38`). 둘 다 `./experiment` 기록과 연결돼 있지 않다 | 변환기 출력, 실행기 입력 |
| R3 | 판정 주체 관문·AI 산출 동일 대조(02 L1) | **부분**: 확인 문장만 | 자기 일치도 가져오기만 확인 문장을 글자 단위로 대조한다(`import_round.py:16-23`), `judge_confirmed=True`(`:64`). AI 파일과 값 대조는 저장소 전체 0건(`rater_kind`·`ai-responses` grep 0). 기준 판본 기록은 모서리 가져오기에서 선택 인자일 때만(`mobile_corner_label_import.py:48,54-55`, `label_criteria.py:27`), 판정자 칸은 없다 | 가져오기, 행 |
| R4 | 촬영 조건 층(03 I1, 04 E2) | **없음**(실행기). 측정값은 있음 | 층의 원천 `measures.json`과 사전 고정 상수(`measure.py:16` `BG_V95_MAX`)는 있다. 실행기 행에는 층 칸이 없다(942행 키: `area, box, group, id, image, image_sha256, split, target`). 03·04의 층 집계는 세션 scratchpad 스크립트다(03:21, 04:35) | 실행기 보고 |
| R5 | 보류 비율(06 M2) | **없음** | 실행기 판정은 0.5 하나다(`regression_audit.py:17` `int(score >= .5)`). 카드 0.20/0.60은 worker 계획 값이다(06 2-1, `fixed_low/high`). 보류 구간 집계는 06의 일회성 계산이다 | 실행기 보고 |
| R6 | 문턱 근처 오류(04 E3) | **없음** | 같음. 저장된 `scores`로 계산은 가능하다(`experiment_record.py:225`) | 실행기 보고 |
| R7 | 사전 고정 판정 규칙·분기 A/B/C(05 4-3, 06 M1) | **부분**: 동결만, 적용 없음 | 실행기는 plan 전체를 그대로 복사해(`:201`) 시작 전에 SHA로 동결한다(`:211`). 그래서 계획 안의 사전 기록은 결과 전 해시가 남는다. 그러나 필수 키 5개 외의 칸은 검사하지 않는다(`:155-157`). 실제 계획에도 `expected_denominators`·`known_biases` 같은 자유 칸이 검사 없이 있다(D2 plan 키). 판정은 FP/FN 상한·새 오답·사람점만이다(`:240-242`). 분기 표 방식의 선례는 `decide.row`(첫 해당 행, `decide.py:61-80`) | 실행기 계획 검사, 사후 판정 도구 |
| 참고 | 연속 미달 횟수(`stop-repeated-misses`) | **없음**(문서만) | 계수 정의는 `COMMON_EXPERIMENT_RECORDS.md:153`. `card_condition/` grep 0건. 같은 평가 자료 시도 수는 사후 도구 `check.py:86-103`(`ledger`)에만 있다 | — |

### 2-2. 재현성·출처 추적에서 추가로 확인한 것

- **앞 담당 집계는 저장소에서 재현할 수 없다.** 02(`:22`)·03(`:21`)·04(`:35`)·05(`:16`, `strata_n.py`)의 스크립트가 모두 세션 scratchpad에 있다. 05·06의 판정 문턱(N_noise, f_hi, DEFF)이 이 수치에 기대므로, 이 수치를 회귀 시험 기대값으로 옮기는 것이 곧 재현 장치다(4절 각 설계의 "회귀" 줄).
- **데이터 버전은 worker가 검사한다.** 계획의 `input_sha256`(행 파일·백본·모듈 해시)은 worker가 대조한다(`corner-grid-average-20261121/worker.py:55`, `edge-back-source-weight-20261030/worker.py:88`). 실행기는 기준 결과의 `record.json` 해시만 대조한다(`experiment_record.py:160-165`). 사이드카도 같은 방식이면 worker마다 검사가 갈린다. 그래서 4-2절은 사이드카 해시를 **실행기**가 검사하게 설계한다.
- **행에 칸을 더해도 평가 자료 해시는 그대로다.** 정체성은 8개 키뿐이다(`cross_review_evidence.py:54`). 반대로 필수 평가는 행 전체를 비교한다(`experiment_record.py:131`). 그래서 층·주체를 행 안에 넣으면 주 평가와 필수 평가의 동작이 갈린다. **행 밖 사이드카(행 id로 연결)**가 안전하다.
- **진단 증거 칸은 쓸 수 없다.** `diagnostic_evidence`는 `experiment_kind == 'diagnostic'`이고 4,000바이트 이하일 때만 받는다(`:248-253`). 모델 실험의 층 보고는 여기에 넣을 수 없다.

## 3. 해야 할 일 목록

| ID | 할 일 | 기대 효과 | 필요한 입력 | 사람 의존 | 선행 조건 | 우선 |
|---|---|---|---|---|---|---|
| X1 | **행 변환기가 제외 건수·행 사실을 함께 낸다**(새 `tools/zone_rows.py`). 4상태를 받아 행 + `exclusions.json` + `row_facts.json`(층·주체·기준 판본) | R1·R2·R4 원천. 분모 치우침을 드러냄 | 답 파일, 리뷰 jsonl, `measures.json`, X3 결과 | 없음 | 사이드카 형식 고정(4-1) | 상 |
| X2 | **실행기가 사이드카를 동결·검사하고 층×점수 구간 표를 결과에 남긴다**(새 `card_condition/experiment_sidecars.py` + 기존 함수 안 2줄) | R2·R4·R5·R6을 모든 실험 기록의 고정 칸으로 | X1 출력 | 없음(통합 승인만) | 4-1 형식 | 상 |
| X3 | **판정 주체 관문**(새 `tools/rater_gate.py`). 답을 모든 AI 파일과 대조, k/n·우연 기준선·판정·파일 해시·시각을 `<답>.provenance.json`에 | R3. 사람 정답 보장 | 답 파일, AI 산출 폴더 | "AI 의심" 처리(02 6절) **사용자 결정** | 없음 | 상 |
| X4 | **가져오기가 `판단 불가`를 받아 별도 상태 파일에 보존**(정답 형식 불변) | R1 | 01 G1 화면 | 화면 변경 **승인** | 01 G1 | 중 |
| X5 | **사전 판정 사후 적용 도구**(05 4-3 블록·분기 A/B/C, 첫 해당 행) | R7. 결과 뒤 기준 변경 차단 | 동결된 plan, result, X2 표, X6 통계 | V·Δ·주 지표 단위 **사용자 결정**, 11-27 재대조 결과 | X2, X6 | 중 |
| X6 | **사진 묶음 통계 도구**(DEFF 보정 Wilson, 사진 단위 부호 뒤집기 순열 검정, 05 S2) | 우연 개선 차단 | 저장 점수·group | 없음 | 없음 | 중 |
| X7 | 연속 미달 계수를 `check.py`의 `ledger` 결과에서 세는 작은 도구 | `stop-repeated-misses` 실측 | 실험 폴더 | 상한 발효는 기존 조건(사용자 승인+통합) | 없음 | 하 |

하지 않을 것: 실행기 판정 문턱을 0.5에서 바꾸기(실행기 계약 `COMMON_EXPERIMENT_RECORDS.md:38`. 다른 문턱은 기술 표로만), 과거 `result.json`·`record.json`·`d2_rows.py` 출력 재작성, 판단 불가·미확인을 정상/결함으로 채운 분모, 사이드카를 행 안에 합치기(2-2절).

## 4. 설계

### 4-0. 구조 제한 대조 (PAIR_CODING §2.1)

| 파일 | 함수 수 지금 | 설계 후 | 메모 |
|---|---:|---:|---|
| `card_condition/experiment_record.py` | 17 | 17 | **이미 초과(기존)**. 함수 추가 금지, 기존 `prepare`·`complete` 안에 호출 1줄씩만 |
| `card_condition/experiment_sidecars.py` (새) | — | 5 | `freeze`, `check_exclusions`, `check_facts`, `check_prereg`, `tally` |
| `tools/zone_rows.py` (새) | — | 5 | `parse`, `build`, `facts`, `write_new`, `main` |
| `tools/rater_gate.py` (새) | — | 5 | `values`, `compare`, `chance`, `verdict`, `main` |
| `tools/mobile_corner_label_import.py` | 3 | 3 | `parse` 안의 상태 집합과 반환값만 |
| `tests/test_experiment_record.py` | 31 | 31 | **이미 초과(기존)**. 새 시험은 새 파일 |

호출 깊이(전이 수):
- 기존 최장: `main → run → _run → complete → experiment → compare_predictions` = 5. **이미 초과(기존)**이고 이번 설계는 이 경로를 늘리지 않는다.
- 새 경로 A: `main → run → prepare → freeze → check_*` = 4. `check_*`는 프로젝트 함수를 부르지 않는 잎이어야 한다.
- 새 경로 B: `main → run → _run → complete → tally` = 4. `tally`도 잎이어야 한다. 그래서 층·구간·보류·문턱 근처를 **한 개의 집계표**(층 × 점수 구간 × 정답)로 내고, 보류 비율·문턱 근처는 이 표에서 읽는 보기로 둔다. 따로 함수를 만들지 않는다.

### 4-1. 사이드카 형식 (X1·X2·X3·X5 공통 계약, 먼저 고정)

계획에 선택 칸 하나를 더한다. 없으면 지금과 똑같이 동작한다(`evaluation_counts`와 같은 하위 호환, `acceptance_caps.py:6-7`).

```json
"sidecars": {
  "exclusions": {"path": "artifacts/<묶음>/exclusions.json", "sha256": "<64hex>"},
  "row_facts":  {"path": "artifacts/<묶음>/row_facts.json",  "sha256": "<64hex>"},
  "bands": [0.2, 0.4, 0.5, 0.6],
  "preregistration": {"rules_sha256": "<사전 블록 파일 해시>", "branch_dependent": true,
                      "branch_observed": "A|B|C", "branch_evidence": {"path": "...", "sha256": "..."}}
}
```

- `exclusions.json`: `{"<칸>": {"<구역>": {"정상": n, "결함": n, "미확인": n, "판단 불가": n, "상자 미확인": {"정상": n, "결함": n, "미확인": n, "판단 불가": n}, "AI 동일": n, "AI 의심": n, "기준 판본 불일치": n}}, "kept_rule": "<문장>"}`. 05 4-1의 고정 칸 다섯 개와 같다.
- `row_facts.json`: `{"<행 id>": {"background": "bg_bright|ok|corner_cut|no_blue_border|unmeasured", "px_per_mm_layer": "<10|10-15.3|>=15.3|unmeasured", "rater_kind": "human|ai_identical|ai_suspect|unknown", "criteria_sha256": "<hex>|버전 미상", "input_hold": true|false}}`. 층 경계는 03 I1·04 E2·06 M2 사전 고정값 그대로다. `measure.py`의 `_measure_sha256`도 함께 적는다.
- `bands`: 기본 `[0.2, 0.4, 0.5, 0.6]`. 04 E3(0.4/0.5/0.6)와 06 M2(0.2/0.6)를 한 줄로 합친 것이다. 기술 표용이며 판정 문턱이 아니다.

### 4-2. 설계 X2: 실행기 사이드카 (변경 변수: 기록 칸, 판정 불변)

- `prepare`(동결 전, `experiment_record.py:182` `check_declared_counts` 바로 뒤) 1줄: `extras = sidecars.freeze(root, plan, reference['rows'], required)`. 그리고 `reference.json` 저장 dict(`:203-206`)에 `sidecars=extras`를 더한다. 사이드카 본문은 `reference.json` 안에 복사되므로 기존 `files` SHA(`:211`)에 자동으로 묶인다.
- `freeze`의 검사(자식 시작 전 거절, 하나라도 어기면 `ValueError` → 기존 `main`이 종료 코드 2):
  1. 경로가 프로젝트 파일이고 실제 SHA가 선언과 같다(`project_file` 재사용 대신 같은 검사를 잎에서 다시 쓴다. 깊이 4 제한 때문).
  2. `check_facts`: `row_facts`의 키 집합 = 주 평가 행 id 집합(필수 평가 행이 있으면 그 id도 포함). 빠짐·남음 모두 거절(조용한 누락 방지).
  3. `check_exclusions`: 각 칸의 `정상+결함` 합 = 그 칸 평가 행의 target 0/1 수(엣지처럼 상자 미확인을 넣은 경우는 `kept_rule`에 적고 `상자 미확인`의 정상·결함을 합에 포함). 맞지 않으면 거절.
  4. `check_prereg`: `branch_dependent`가 참이면 `branch_observed ∈ {A,B,C}`이고 근거 파일 SHA가 맞아야 한다. **분기는 결과보다 먼저 고정된다**(05 4-3 마지막 줄). `rules_sha256` 파일이 있으면 해시 대조.
- `complete`(`:256-257` `acceptance_caps` 뒤) 1줄: `if ref.get('sidecars'): result['strata_table'] = sidecars.tally(result['rows'], result['scores'], ref['sidecars'])`.
- `tally` 출력: `[{"background":…, "px_per_mm_layer":…, "rater_kind":…, "band":"<0.2|0.2-0.4|…", "target":0|1, "n":k}]`와 `{"before": 같은 표}`(대조 점수 `before_scores`). 판정·`acceptance_passed`는 바꾸지 않는다.
- 문서: `COMMON_EXPERIMENT_RECORDS.md`에 "사이드카(선택)" 절 하나. `zero-denominator-unmeasured` 절처럼 "칸이 없으면 그대로 실행"을 명시한다.

**회귀(`regression-for-every-fix`, 실제 입력):**
1. 사이드카 없는 계획: 기존 `tests/test_experiment_record.py`의 시험 27개(`def test` 수)를 고치지 않고 통과. `result.json` 키 집합이 지금과 같음.
2. `row_facts`에서 행 1개를 지운 사이드카 → 자식 시작 전 거절, 실험 폴더 미생성.
3. SHA 한 글자 바꿈 → 거절.
4. 실제 자료 재현(자료가 없는 checkout에서는 "미검증"으로 건너뜀): `20261121T050740-8588eeb0`의 행·점수 + `measures.json`으로 `tally`를 돌리면
   - 배경 층(0.5 기준): 밝음 누락 52/185·오탐 39/336, 어두움 누락 28/187·오탐 40/164(03 2-3, 04 2-3 재현값).
   - 구간: 누락 <0.4 63·0.4~0.5 26, 오탐 0.5~0.6 35·≥0.6 54(04 E3). 
   - 보류(0.2/0.6): 정상 249/238/54, 결함 15/103/283(06 2-4).
5. 분기 미기재(`branch_dependent=true`, `branch_observed` 없음) → 거절.

### 4-3. 설계 X1: 행 변환기 (변경 변수: 변환 출력 하나, 행 내용 불변)

- 새 `tools/zone_rows.py`. `d2_rows.py`는 고치지 않는다(D2는 1회 사용한 과거 평가다. 호출자·시험 없음, grep 0건).
- `parse`: `id/side=확인|미확인;box:…;구역:상태`. 상태 집합 = `{정상, 결함, 미확인, 판단 불가}`. **그 밖의 문자열은 줄 번호와 함께 거절**(`d2_rows.py:36`처럼 조용히 버리지 않는다).
- `build(answers, info, need_ok, provenance)`: 행은 `정상|결함`만. 나머지는 `exclusions`에 칸·구역·사유별로 센다. 상자 미확인 처리는 인자로 받고 그대로 `kept_rule`에 문장으로 남긴다. `provenance`(X3 출력)에서 `AI 동일`이면 행에서 빼고 `AI 동일`로 센다. `AI 의심`은 사용자 결정 전까지 행에 두고 `row_facts.rater_kind`로만 표시한다(가정 없이 바꿀 수 있게).
- `facts`: `measures.json`의 `status`·`ppm`을 `id|image_sha256`로 붙인다(04 T1과 같은 키). 측정이 없는 행은 `unmeasured`.
- `write_new`: 세 파일을 `open('x')`로 쓴다(덮어쓰기 금지, `label_criteria.py:26`과 같은 원칙). 하나라도 실패하면 이번에 쓴 파일을 지운다.

**회귀(실제 입력):**
1. `d1-labels-20261103/cor-answers.txt`, `need_ok=True` → 행 508개, id·target·box 순서가 `20261103T131123-7fa5d398/observations.json` 행과 같음. 제외 = 확인 상자 미확인 16 + 상자 미확인 28(미확인 20·정상 3·결함 5)(이번 O2).
2. `edge-zone-answers.txt`, `need_ok=False` → 942행(0: 660, 1: 282), 제외 미확인 2, `kept_rule`에 "상자 미확인 24구역 포함"(O2, `d2_rows.py:68`).
3. 같은 파일에 `판단 불가` 한 구역을 넣은 합성 줄 → 행에서 빠지고 `판단 불가: 1`로 셈.
4. `애매` 같은 모르는 상태 → 거절(조용한 누락 방지).

### 4-4. 설계 X3: 판정 주체 관문 (변경 변수: 가져오기 전 검사 하나)

02 L1 설계를 따른다. 운영 세부만 고정한다.
- `values`: 두 형식을 읽는다. `zN=값`(봉인 점검·재시험 화면)과 `구역:상태`(모바일 화면).
- `compare`: 지정 폴더(기본 `ai-responses/`, `ai-reference/`)의 **모든** AI 파일과 대조해 파일마다 k/n·SHA·수정 시각을 남긴다. 최댓값만 남기지 않는다. 이번 O3처럼 pass1 50/64, final 64/64가 함께 있어야 기록이 해석된다.
- `chance`: 같은 답의 값 분포로 우연 일치 Σp²를 계산한다.
- `verdict`(사전 고정, 02 L1 그대로): 최대 k/n = 1.0 → `ai_identical`. 최대 k/n이 우연 기준선 Wilson 95% 상한 초과 → `ai_suspect`. 그 밖 → `no_match_found`(사람 증명 아님). 확인 문장(`import_round.confirmed`와 같은 글자 대조)이 없으면 `unknown`. Wilson은 기존 식을 빌려 쓴다(`stats.py:25`와 같은 `borrow`).
- 출력: `<답>.provenance.json`, `open('x')`. 답 파일 수정 시각이 AI 파일보다 늦으면 그 사실도 칸으로 남긴다(02 2-3의 A2·B2 시각).

**회귀(실제 입력):**
1. `cohort2-retest-20261125/responses/A2.txt` → final 64/64로 `ai_identical`, pass1 56/64도 기록.
2. 같은 폴더 `B2.txt` → pass1 50/64·final 64/64 두 줄 모두 기록, 판정 `ai_identical`.
3. `cohort2-label-check-20261124/responses/input-1.txt` 대 `screen-1-AI-v3-final-20261124.txt` 62/64 → `ai_suspect`(기준선 상한을 넘는지 시험에서 계산).
4. 같은 구역 수의 무작위 합성 답(시드 고정) → `no_match_found`.

### 4-5. 설계 X4·X5·X6·X7 (요약)

- **X4**(01 G1 화면과 한 task): `mobile_corner_label_pages.py:23`의 `NEXT`에 `판단 불가`를 넣고, `mobile_corner_label_import.parse`(`:23,25`)가 `판단 불가`를 받게 한다. 정답 형식(`region_labels` 0/1/None, `validate_annotations`)은 바꾸지 않는다. 대신 `<out>.states.json`(`{구역 id: "미확인"|"판단 불가"}`)을 `open('x')`로 쓴다. 회귀: 기존 `tests/test_corner_label_round_trip.py` 방식으로 4상태 × 4구역을 눌러 가져온 값과 대조(`label-screen-round-trip`).
- **X5**: 새 `tools/diagnostics/prereg-verdict-<날짜>/verdict.py`. 동결된 `plan.json`의 사전 블록(05 4-3 그대로)과 `result.json`·`strata_table`을 읽어 성공 (1)~(5)와 실패 문장을 첫 해당 행으로 고른다(`decide.row` 방식). 분기 B면 v2 칸을 지우고 "정식 값 없음", C면 "조건부". 실행기 판정(`acceptance_passed`)은 건드리지 않는 사후 기술 판정이다. 회귀: 05 4-3의 예(m=56, f_hi 0.081 → N_noise 10, c−b=10이면 "잡음 폭 안").
- **X6**: 새 `tools/diagnostics/cluster-stats-<날짜>/stats.py`. DEFF 보정 Wilson, 사진 부트스트랩, 사진 단위 순열 검정. 회귀: 05 2-2 값(개발 오탐 DEFF 1.33, 누락 1.44)과 S4(E 대 평균 정상 b=30·c=26). `size.py`는 고치지 않는다(05가 정본 141·236·249·454를 이미 재현했다).
- **X7**: 새 파일(기존 `check.py`는 함수 7개로 한도라 더하지 않는다). `check.ledger`를 불러 같은 `cohort_sha256`에서 `experiment_kind != 'diagnostic'`·completed인 실행의 연속 `acceptance_passed=false` 수를 센다(`COMMON_EXPERIMENT_RECORDS.md:153` 정의). 상한 발효 조건은 그대로다. 회귀: 942 자료의 마지막 세 실행(coverage·orientation·phase-train, 06 2-2)을 넣으면 3이 나와야 한다(발효 전이라 "참고 값"으로 출력).

### 4-6. 구현 task 계약과 병렬 가능 여부

모든 task는 `./develop -- <수정 명령>` 안에서 수정하고, 실제 실험·추론은 하지 않는다(PAIR_CODING §1). 실제 자료가 필요한 회귀는 자료 없는 worktree에서 "미검증"으로 건너뛰고, 통합 뒤 기본 checkout에서 현재 메인이 돌린다.

| task | allowed_files | checks | 사람 의존 | 선행 | 병렬 |
|---|---|---|---|---|---|
| T0 형식 고정 | `docs/collaboration/tasks/record-sidecars-20261126.md`(4-1 형식 그대로) | 형식 문서 리뷰 | 없음 | — | **먼저 단독** |
| T1 = X1 | `tools/zone_rows.py`(새), `tests/test_zone_rows.py`(새) | 4-3 회귀 1~4, `git diff --check` | 없음 | T0 | T2·T3·T4와 **병렬 가능**(파일 겹침 없음) |
| T2 = X2 | `card_condition/experiment_sidecars.py`(새), `card_condition/experiment_record.py`(2줄+dict 1칸), `tests/test_experiment_sidecars.py`(새), `COMMON_EXPERIMENT_RECORDS.md`(절 하나) | 4-2 회귀 1~5, 기존 `tests/test_experiment_record.py`·`tests/test_acceptance_caps.py` 그대로 통과 | 없음(main 통합은 승인 절차) | T0 | T1·T3·T4와 **병렬 가능**. 공용 `experiment_record.py`는 이 task만 소유 |
| T3 = X3 | `tools/rater_gate.py`(새), `tests/test_rater_gate.py`(새) | 4-4 회귀 1~4 | "AI 의심" 처리 결정(판정 칸 이름만 영향, 구현은 가능) | T0 | **병렬 가능** |
| T4 = X4 (+01 G1) | `tools/mobile_corner_label_pages.py`, `tools/mobile_corner_label_import.py`, `tests/test_corner_label_round_trip.py`의 새 짝 파일 `tests/test_corner_label_four_state.py`(새) | 4상태 왕복, 기존 왕복 시험 통과 | **화면 변경 승인 필요** | 승인 | 승인 뒤 **병렬 가능** |
| T5 = X6 | `tools/diagnostics/cluster-stats-<날짜>/stats.py`(새), 시험 1개(새) | 05 2-2·S4 수치 재현 | 없음 | 없음 | **병렬 가능** |
| T6 = X5 | `tools/diagnostics/prereg-verdict-<날짜>/verdict.py`(새), 시험 1개(새) | 05 4-3 예, 분기 A/B/C 각 1건 | **V·Δ·주 지표 단위 결정**, 11-27 재대조 | T2·T5 | **직렬**(T2·T5 뒤) |
| T7 = X7 | 새 진단 파일 1개 + 시험 1개 | 4-5 회귀 | 없음 | 없음 | 병렬 가능, 우선 하 |

각 task 계약의 `structure` 칸에는 4-0 표의 전/후 함수 수와 경로 A·B의 전이 수를 그대로 적는다. 롤백은 새 파일 삭제와 `experiment_record.py` 2줄 되돌리기(`git revert <통합 SHA>`)다. 사이드카가 없는 과거 계획·결과는 어떤 task에서도 바뀌지 않는다.

## 5. 앞 담당 의견에 대한 반박/보완

- **02 L3 보완(원인 확정).** "D2 엣지가 상자 미확인 24구역을 포함한 이유는 미확인"(02 2-2·6절)은 코드로 확인된다: `d2_rows.py:68`에서 엣지만 `need_ok=False`다. 의도는 기록에 없다(미확인). X1은 이 차이를 인자와 `kept_rule` 문장으로 기록에 남긴다. 소급해 맞추지 않는다는 02의 원칙은 유지한다.
- **02 6절 질문 답(B2 50/64 대 64/64).** 대조 파일 차이다. pass1이 50/64, final이 64/64다(O3). 그래서 X3은 AI 파일 하나만 고르지 않고 폴더의 모든 파일을 대조해 각각 기록한다.
- **02 L1 보완(위치).** 관문을 가져오기 도구 안에 넣으면 `import_round.py`·모서리·표면 가져오기에 각각 넣어야 한다. 별도 CLI(X3)로 두고 변환기(X1)가 그 출력을 읽으면 한 곳에서 끝난다. 확인 문장 검사는 이미 있는 `import_round.confirmed`와 같은 글자 대조를 쓴다.
- **01 G1·02 2-1 보완(저장 형식).** `판단 불가`를 `region_labels`에 넣으면 기존 정답 검사(`validate_annotations`)와 모든 소비 코드를 바꿔야 한다. 정답 형식은 두고 상태 파일을 옆에 두는 쪽(X4)이 변경이 작고 과거 라벨과 섞이지 않는다.
- **03 I1·04 E2·06 M2 보완(한 표로).** 셋이 각자 표를 제안했다. 실행기 쪽에서는 층 × 점수 구간 × 정답 한 표면 셋 다 읽힌다(4-2). 함수 하나(잎)로 끝나 호출 깊이 제한도 지킨다.
- **05 4-3·06 M1 보완(사전 고정의 증거).** 05·06은 "commit 금지라 첫 저장뿐"이라고 했다. 실행기 경로를 쓰면 plan 전체가 결과 전에 SHA로 동결된다(`experiment_record.py:201,211`). 단, 이 동결은 자식 실행 직전이다. 분석 문서처럼 실행기 밖의 사전 기록은 여전히 git commit(사용자 승인)이 유일한 증거다. X2의 `check_prereg`는 분기 값이 비어 있으면 실행을 거절해, "분기를 본 뒤 결과"의 순서를 기계로 강제한다.
- **05 S2 보완.** 05는 "계산 도구는 승인 뒤 별도 작업"이라 했다. X6은 그 작업의 계약이고, 회귀 기대값은 05의 수치다. 이 수치는 지금 scratchpad 스크립트에만 있어(2-2절) 시험으로 옮기기 전까지 재현 근거가 없다.
- **06 M1 주의.** 새 기준 작동점(0.30)은 실행기 판정에 넣을 수 없다(`:153`, `regression_audit.py:17`). X2의 `bands`에 0.3을 넣는 것은 기술 표일 뿐이다. 실행기 판정 문턱을 바꾸려면 COMMON 계약·실행기·시험을 함께 바꾸는 별도 결정이 필요하다(`COMMON_EXPERIMENT_RECORDS.md:38`).

## 6. 다음 담당에게 넘기는 질문·미확인 사항

- 사용자 결정 필요: T4 화면 변경 승인(01 G1), X3 "AI 의심"을 행에서 뺄지 표시만 할지, X5의 V·Δ·주 지표 단위(05 S5), 이 문서와 05·06 사전 블록의 commit 승인.
- 미확인: 개발 946행 `rows.json`을 만든 코드(plan에는 해시만 있다), 엣지 `need_ok=False`의 의도, 엣지·표면 화면에 `.criteria.json`을 넓힐지(`QUALITY_RULES.md:170`은 모서리만 지원).
- 미검증: 4절의 모든 회귀는 아직 시험 코드가 없다. 실제 자료 재현값(4-2 회귀 4)은 기본 checkout에서만 돌 수 있다.
- 통합 담당에게: T2가 `experiment_record.py`의 유일한 소유자다. 같은 시기 다른 task가 이 파일을 건드리면 직렬화해야 한다(PAIR_CODING §3).

## 적용 품질 규칙

적용: `short-request-reading`, `regression-for-every-fix`(모든 설계에 실제 입력 회귀), `label-screen-round-trip`(X4), `label-provenance`(row_facts의 기준 판본, 소급 없음), `zero-denominator-unmeasured`(acceptance_caps 선례 대조), `stop-repeated-misses`(X7, 발효 전 표시). 못 지킨 것: 설계만이라 회귀 시험을 실제로 돌리지 못했다. 추가한 점검: 실행기 본체의 기존 구조 초과(함수 17·깊이 5)를 확인해 새 코드를 잎 함수로 제한, 행 정체성 키와 필수 평가 행 비교의 차이(사이드카를 행 밖에 두는 근거), 앞 담당 집계의 재현 불가(scratchpad).

## 롤백

이 파일 삭제. 다른 파일은 바꾸지 않았다.
