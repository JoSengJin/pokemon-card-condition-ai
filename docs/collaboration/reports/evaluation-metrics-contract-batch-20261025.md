# 평가 수치 계약·반례 검증 — 2026-10-25

task `evaluation-metrics-contract-batch-20261025`. 기준은 base `aa3e74583f8d2213b9dbad8f664c0a1ce0f8f703`이고 시작 HEAD는 `024e64fad3bc397eeae80a294f2d63a916e78a57`이다.

고정된 합성 정답과 이미 계산된 확률만으로 세 소스의 수치 계약을 독립 검증한다. 모델 학습·추론·실자료 열람·외부 AI는 0회다. 실제 모델 성능·정확도·진척률 30/100은 갱신하지 않는다.

## 1. 입력 경계와 손계산 기준

### 대상과 실제 호출 경로 (읽기 전용 확인)

| 함수 | 파일 | 호출자 |
|---|---|---|
| `error_rates(counts)` | quality_rates | comparison, region_evaluation, side_evaluation, visibility_compare, observation_crossfit, score_diagnostics |
| `rate_change(reference, candidate)` | quality_rates | comparison, visibility_compare, observation_nested |
| `compare_predictions(truth, before, after)` | regression_audit | experiment_record, cross_review_evidence |
| `compare_runs(...)` (중첩 `index`) | regression_audit | 저장소 안에 호출자 없음. 기존 테스트만 사용 |
| `score_diagnostics(predictions, supported)` | score_diagnostics | comparison, visibility_compare, visibility_model, observation_crossfit, observation_heldout |
| `group_abstention(predictions, key, low, high)` | score_diagnostics | `score_diagnostics` 내부 |

### upstream에서 검증되는 입력 (leaf에 중복 검증을 붙이지 않음)

- **확률의 유한성과 [0, 1] 범위:**
  - `compare_predictions`는 스스로 검사한다.
  - `score_diagnostics`는 검사하지 않는다. 호출자 `comparison.py`가 "Invalid region probabilities"로 먼저 거절한다. 이 전제를 벗어난 값(NaN 등)에 대한 동작은 지원 범위 밖으로 기록만 한다.
- **정답 값:** manifest·annotation 검증(`regions.validate_annotations`)이 0, 1, None만 허용한다.
  - `score_diagnostics`는 None을 known 분모에서 뺀다.
  - `compare_predictions`는 None과 bool을 `ValueError`로 거절한다.
- **`compare_runs` 행 필드:** `id`, `group`, `side`, `split`, `image_sha256`, `card_box`, `box`, `labels[label]`가 있다고 전제한다. 필드가 없으면 `KeyError`가 나는데, 이는 지원하지 않는 불완전 레코드이며 오류 종류를 바꾸지 않는다.
  - ID는 문자열로 전제한다. 정수와 문자열이 섞이면 정렬에서 `TypeError`가 난다.
  - unknown 정답이 양쪽에 모두 있으면 비교 전체가 `compare_predictions`에서 거절된다. 행을 조용히 버리지 않으며, unknown 필터링은 호출자 책임이다.

### 기존 수치 계약 (검증 기준)

- 판정 임계값은 `score >= 0.5`이면 결함이다.
- FNR = FN/(TP+FN), FPR = FP/(TN+FP). 분모가 0이면 None이며 0%로 보고하지 않는다.
- `rate_change`는 양성·정상 분모가 같을 때만 비교한다. 변화는 `100 × (candidate − reference)` %p다.
  - `errors_jointly_improved`는 두 오류율이 모두 평가 가능하고, 둘 다 늘지 않았으며, 하나 이상 줄었을 때만 true다.
- `compare_predictions`의 결과 필드:
  - `aggregate_improved`: FN·FP 모두 늘지 않고 하나 이상 줄었음
  - `informative_improvement`: 위 조건에 더해 두 정답 종류가 모두 있고, after 예측이 한 종류로 고정되지 않음
  - `no_new_errors`: 새 누락·새 오탐이 모두 없음
  - 세 필드는 서로 다른 뜻이다.
- **AUROC:** 서로 다른 점수값을 내림차순으로 묶어 ROC 사다리꼴을 적분한다. 양성-음성 쌍마다 승리 1, 동점 0.5, 패배 0을 준 평균(Mann–Whitney)과 같아야 한다.
- **AP:** 서로 다른 점수값 묶음마다 `(recall_k − recall_{k−1}) × precision_k`를 더한다. 동점 묶음은 한 단계로 처리하며 보간하지 않는다. 동점이 없으면 양성 순위별 precision의 평균과 같다.
- 양성이나 음성 중 한 종류만 있으면 AUROC·AP·balanced accuracy는 None이다.
- **보류:**
  - 각 `(low, high)`에서 `value < low`는 정상으로 수용, `low ≤ value < high`는 보류, `value ≥ high`는 결함으로 수용한다.
  - `(.5, .5)`는 raw 0.5 판정과 같다.
  - `risk_known`은 수용된 known 행 기준의 micro 위험이다. 원래 누락률이 아니다.
  - `mean_group_risk`는 수용 행이 있는 실물의 위험 평균이다.
  - `accepted_groups`는 수용 행이 있는 실물 수다.
  - `zero_accepted_known_groups`는 known 행이 있는데 모두 보류된 실물 수다.

### 손계산 기준표

기대값은 아래 표에서 정한다. 구현 함수를 다시 호출해 기대값을 만들지 않는다.

**혼동행렬·%p** (reference R = tp3 fn1 tn6 fp4)

| 후보 | 양성/정상 | FNR | FPR | accuracy | ΔFN %p | ΔFP %p | jointly |
|---|---|---|---|---|---|---|---|
| R | 4/10 | 1/4 = .25 | 4/10 = .4 | 9/14 | — | — | — |
| tp4 fn0 tn7 fp3 | 4/10 | 0 | .3 | 11/14 | −25 | −10 | true |
| tp2 fn2 tn5 fp5 | 4/10 | .5 | .5 | 7/14 | +25 | +10 | false |
| tp2 fn2 tn9 fp1 (accuracy만 개선) | 4/10 | .5 | .1 | 11/14 | +25 | −30 | false |
| tp3 fn1 tn6 fp4 (동일) | 4/10 | .25 | .4 | 9/14 | 0 | 0 | false |

정상만 있는 쌍(tp0 fn0 tn3 fp2 → tn4 fp1): FNR None, ΔFP −20 %p, jointly false(누락률을 평가할 수 없음).

**AUROC·AP**

| 사례 | 양성 점수 | 음성 점수 | AUROC (쌍별) | AP |
|---|---|---|---|---|
| 완전 분리 | .9 .8 | .2 .1 | 4/4 = 1 | 1 |
| 완전 역순 | .1 .2 | .8 .9 | 0/4 = 0 | 1/2·1/3 + 1/2·1/2 = 5/12 |
| 전부 동점 | .5 .5 | .5 | 1/2 = .5 | 1·2/3 = 2/3 |
| 일부 동점 | .8 .6 | .6 .3 | (1+1+.5+1)/4 = .875 | 1/2·1 + 1/2·2/3 = 5/6 |
| 3대3 혼합 | .9 .4 .3 | .7 .4 .1 | (3+1.5+1)/9 = 11/18 | 1/3·1 + 1/3·1/2 + 1/3·3/5 = 7/10 |
| 1대3 동점 포함 | .5 | .6 .5 .4 | (0+.5+1)/3 = .5 | 1·1/3 = 1/3 |

**보류와 실물** (`(.3, .7)`)

| 실물 | 정답/점수 | 처리 |
|---|---|---|
| X | 1/.9, 0/.8, 0/.75 | 3행 수용(오류 2), 위험 2/3 |
| Y | 1/.1 | 수용(정상 판정, 누락), 위험 1 |
| Z | 0/.5, 1/.4 | known 2행 모두 보류 → `zero_accepted_known_groups`에 포함 |
| U | None/.95 | known 0, unknown 1. known 분모에서 제외되지만 `by_group`에는 남음 |

- micro 위험 = 3/4 = .75
- 실물별 평균 = (2/3 + 1)/2 = 5/6
- `accepted_groups` = 2, `zero_accepted_known_groups` = 1

## 구조 제한 (전)

| 파일 | 함수 정의 수(중첩 포함) |
|---|---|
| card_condition/quality_rates.py | 2 (`error_rates`, `rate_change`) |
| card_condition/regression_audit.py | 3 (`compare_predictions`, `compare_runs`, 중첩 `index`) |
| card_condition/score_diagnostics.py | 2 (`group_abstention`, `score_diagnostics`) |

파일을 넘는 주요 호출 경로(전이 수):
- `comparison` → `score_diagnostics` → `quality_rates.error_rates` (2)
- `score_diagnostics` → `group_abstention` (같은 파일, 1)
- `comparison` / `visibility_compare` / `observation_nested` → `rate_change` → `error_rates` (2)
- `experiment_record` / `cross_review_evidence` → `compare_predictions` (1)
- `compare_runs` → `index`, `compare_predictions` (같은 파일, 1)

정적으로 확인하지 못한 호출은 없다. 세 파일 사이에 순환 import는 없다(`score_diagnostics`가 `quality_rates`만 import한다).

## 2–6단계 결과

### 커밋 순서

| 단계 | 커밋 | 내용 |
|---|---|---|
| 1 | `383d13dfa1484a7dad2168e73687ce10a041362e` | 이 보고서 1절: 입력 경계·손계산 기준·구조 제한(전) 고정, task status `implementing` |
| 2 | `247b7a9662c686784a5375044b54313cf3900415` | `tests/test_metric_denominator_contract.py`, `tests/test_paired_population_contract.py` |
| 3 | `66b2c3e8abbb89428d24c9748ed72f2331a216df` | `tests/test_ranking_abstention_contract.py` |
| 4 | `65c394c227877ff2a18c94988f3e93575af47a21` | `tests/test_metric_metamorphic_contract.py` |
| 5 | `085a498c08aba52504fa9fd454a45b5cc0aa881f` | mutation 대조로 드러난 검사 빈틈 보강(보류 경계에 실물별 집계 대조) |
| 6 | 이 문서 커밋 | 최종 보고·task 기록, status `ready_for_review` |

**결론: 재현된 소스 결함은 없다.** 세 소스(`quality_rates.py`, `regression_audit.py`, `score_diagnostics.py`)는 base 대비 diff가 0이다. 계약에 따라 회귀 검사만 남겼다.

### 사례별 검사 대응

| 계약 항목 | 검사(파일::이름) | 결과 |
|---|---|---|
| 클래스별 분모, 분모 0 → None | denominator::`test_each_class_has_its_own_denominator_and_zero_is_none` | 통과 |
| 같은 분모의 %p, 함께 개선·악화, accuracy만 개선, 변화 없음 | denominator::`test_percentage_points_on_identical_denominators` | 통과 |
| 한 종류만 평가 가능하면 jointly false | denominator::`test_one_class_change_is_not_a_joint_improvement` | 통과 |
| 비율이 같아도 분모가 다르면 거절 | denominator::`test_equal_rates_on_other_denominators_are_refused` | 통과 |
| 잘못된 counts 거절 | denominator::`test_malformed_counts_are_rejected` | 통과 |
| 행별 전이(새 누락·새 오탐·회복) | paired::`test_transitions_are_counted_per_row` | 통과 |
| aggregate / informative / no_new_errors 구분 | paired::`test_improvement_flags_have_different_meanings` | 통과 |
| 행 순서 불변(ID 정렬) | paired::`test_row_order_does_not_change_the_result` | 통과 |
| group·side·split·image_sha256·card_box·box 변경, ID 누락·추가·교체·중복, 길이 불일치 거절 | paired::`test_changed_population_or_evidence_is_refused` | 통과 |
| unknown이 정상 0이 되지 않음, 양쪽 unknown은 전체 거절 | paired::`test_unknown_truth_never_becomes_normal` | 통과 |
| 유효 입력 손계산 | paired::`test_valid_paired_input_is_counted_by_hand` | 통과 |
| AUROC·AP 손계산 6사례 × 행 순서 3가지, 독립 쌍별 계산 | ranking::`test_auroc_and_ap_match_hand_calculation` | 통과 |
| 한 종류·unknown만·빈 자료 → None | ranking::`test_single_class_or_unknown_only_sets_report_none` | 통과 |
| 5개 `(low, high)`의 반열린 경계와 실물별 집계 일치 | ranking::`test_each_trial_uses_half_open_boundaries` | 통과 |
| `.5/.5` = raw 0.5 판정 | ranking::`test_raw_half_trial_agrees_with_rates_at_05` | 통과 |
| micro 위험·실물 평균·accepted_groups·전부 보류된 실물·unknown만 있는 실물 | ranking::`test_micro_risk_card_mean_and_deferred_cards_are_distinct` | 통과 |
| 작은 전수: AUROC = 쌍별 계산(동점 포함), 동점 없는 AP = 순위별 precision 평균 | metamorphic::`test_exhaustive_auroc_and_untied_ap_match_independent_formulas` | 통과 |
| 행 순열 불변(지표·보류·paired 전이) | metamorphic::`test_row_permutations_change_nothing` | 통과 |
| cohort 복제: 개수는 2배, 비율·순위·위험은 불변 | metamorphic::`test_duplicated_cohort_doubles_counts_but_keeps_rates` | 통과 |
| before = after → 새 오류 0, %p 0, 개선 아님 | metamorphic::`test_identical_runs_report_no_change` | 통과 |
| 0.5 경계를 넘으면 혼동행렬 한 칸만 이동 | metamorphic::`test_crossing_the_threshold_moves_exactly_one_confusion_cell` | 통과 |

손계산 기대값은 1절 표에서 가져왔다. 기대값을 구현 함수로 다시 만들지 않았다.
- 독립 비교: AUROC는 쌍별 승·무·패 계산, 동점 없는 AP는 순위별 precision 평균 공식이다.
- 복제 검사는 순수 집계(`score_diagnostics`, `error_rates`)에만 적용했다. `compare_runs`의 중복 ID 거절과 섞지 않았다.
- 작성 중 제 손계산 실수(전이 표 혼동행렬의 tn·fn) 1건을 실행 전에 바로잡았다. 코드 결함이 아니다.

### 작은 전수 범위와 시간

- 동점 포함 cohort: 점수 `{.2, .5, .8}`, 2–4행, 두 정답 종류 포함. 18 + 162 + 1,134 = 1,314개.
- 동점 없는 cohort: 점수 `{.1, .3, .6, .9}`의 순열, 2–4행. 24 + 144 + 336 = 504개.
- 순열·복제 검사는 3행 cohort 162개 × 순열 6가지.
- 무작위·대량 fuzz·새 라이브러리 없음. 시간 상한을 30초로 단언했으며, 실제 신규·기존 7모듈 전체가 약 0.22초다.

### mutation 대조 (임시 복사본, 신규 4모듈만 실행)

13개 변형 중 12개가 처음부터 검출됐다.
- FNR 분모를 전체로 바꿈
- 분모 동일 검사 제거
- jointly 판정에 감소 조건 제거
- 임계값을 `>`로 바꿈
- 새 누락과 새 오탐을 서로 바꿈
- side 비교 제거
- ID 정렬 제거
- AUROC를 사각형 적분으로 바꿈
- AP precision 변형
- 수용 조건을 `v <= low`로 바꿈
- 실물 평균을 micro로 바꿈
- unknown만 있는 실물을 zero_accepted로 셈

`group_abstention`의 보류 구간을 `low < value < high`로 연 변형은 살아남았다. 새 경계 검사가 실물별 집계를 대조하지 않았기 때문이다. 기존 `test_score_diagnostics`는 이를 잡지만, 새 검사만으로는 빈틈이었다. 5단계(`085a498`)에서 실물별 대조를 추가했고, 이후 같은 변형이 실패 4건으로 검출된다. 이 보강은 소스 결함 수정이 아니다.

### 구조 제한 (후)

| 파일 | 함수 정의 수 (전 → 후) |
|---|---|
| card_condition/quality_rates.py | 2 → 2 (변경 없음) |
| card_condition/regression_audit.py | 3 → 3 (변경 없음) |
| card_condition/score_diagnostics.py | 2 → 2 (변경 없음) |
| tests/test_metric_denominator_contract.py | 신규 5 |
| tests/test_paired_population_contract.py | 신규 7 (`rows` 1 + 검사 6) |
| tests/test_ranking_abstention_contract.py | 신규 7 (`prediction`, `pairwise_auc` + 검사 5) |
| tests/test_metric_metamorphic_contract.py | 신규 6 (`cohorts` 1 + 검사 5) |

- 모두 7개 이하이며 lambda는 없다.
- 주요 호출 경로는 1절과 같다(최대 전이 2). 소스를 바꾸지 않았으므로 변화가 없다.
- 신규 테스트의 경로: `test_metric_metamorphic_contract` → `test_ranking_abstention_contract.prediction/pairwise_auc`(1) → `score_diagnostics` → `group_abstention`·`error_rates`(최대 3). 제한 4 이내다.
- 정적으로 미확인인 호출이나 순환은 없다.

### 검사 결과

- `PYTHONPATH=tests .venv/bin/python -m unittest test_quality_rates test_regression_audit test_score_diagnostics test_metric_denominator_contract test_paired_population_contract test_ranking_abstention_contract test_metric_metamorphic_contract -v` → 34개 통과, 종료코드 0.
  - 기존 13개: 1 / 8 / 4
  - 신규 21개: 5 / 6 / 5 / 5
- `.venv/bin/python -m compileall -q card_condition/quality_rates.py card_condition/regression_audit.py card_condition/score_diagnostics.py` → 종료코드 0.
- `git diff --check aa3e745… HEAD` → 통과.
- base 이후 변경 파일: allowed_files 중 신규 테스트 4개와 문서 2개, 그리고 Codex 배정 커밋의 prompt 문서. 세 소스는 변경하지 않았다.
- 가상환경: 이 worktree의 `.venv`. 세 모듈 import 시 torch·PIL이 로드되지 않는 것을 확인했다.

### 미검증·리스크·롤백

- 미검증:
  - 기존 ML 의존 통합 검사(Codex 몫)
  - 실제 평가 결과와 실자료(이번 범위 밖, 열람하지 않음)
  - upstream 전제를 벗어난 입력: `score_diagnostics`의 NaN·범위 밖 확률, `compare_runs`의 필드 누락(`KeyError`), 정수·문자열이 섞인 ID(`TypeError`). 계약대로 오류 종류를 바꾸지 않고 전제로만 기록했다.
- 보류·결정 필요: 없음.
- 리스크:
  - 합성 cohort 검증이며 실제 모델 성능이나 일반화를 말하지 않는다.
  - AP는 동점 묶음을 한 단계로 처리하는 비보간 정의다. 다른 정의(보간 AP 등)와 수치가 다를 수 있다.
  - micro 위험과 실물 평균 위험의 차이는 의도된 가중 차이이며 결함이 아니다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 위 커밋을 역순으로 revert한다. 테스트·문서만 추가했으므로 모델·라벨 복구가 필요 없다. 진척률 30/100·배점·품질 기준은 그대로다.


## Codex 통합 검토·HTML 보고

전달6개 커밋의 부모 순서·dispatch 이후 허용 파일6개·깨끗한 Claude worktree를 확인해 지정 순서로 main에 cherry-pick -x했다. 검증 소스 SHA: cfe98412fd1f6248a0589c69fa97d167a3d9ce99. 신규21+기존수치13+기존통합143=177 tests가 기본 checkout에서 통과했다. 실제 모델 source 세 파일은 aa3e745 대비 diff0이다. AST로 신규 테스트 함수 수 5/7/7/6을 확인했다. 작은 전수 검사는 지정 테스트의 일부로 재실행됐다. Claude의 mutation13개는 이번에 재실행하지 않았다.

근거: artifacts/evaluation-metrics-integration-20261025/tests.log 및 verification.json. 합성 손계산과 실제 테스트 기대값을 대조했으며 재현된 source 결함은 없다. 새 모델 학습·추론·실자료 평가·외부 AI0회, 일반화/품질 개선 미평가, usable-card-analysis-v1.0 30/100 유지.

Claude 인계에는 추가 HTML이 없으므로 Codex가 사용자 요청의 HTML 보완 계약에 따라 같은 이름의 .html 보고서를 작성했다. 실제 로그·고정 진척 정본을 대조했고 외부 의존·개인 경로·실자료 없이 정적 HTML로 기록한다. 열기 요청/렌더 확인 결과는 최종 인계에서 별도로 보고한다. 테스트한 SHA와 HTML/문서 커밋 SHA는 구분한다.

롤백: 이번 Codex 보고서/HTML 커밋과 통합 커밋 cfe9841,7e15b56,3a5c6a3,780a318,aab81e9,082c90b을 최신부터 revert하고 관련 검사 후 일반 push한다. 원본 모델/라벨 변경이 없어 별도 복구는 필요 없다.

HTML 열기 결과: macOS open -a Google Chrome 명령 종료코드0으로 열기 요청에 성공했다. 브라우저 자동화가 선택한 표면은 별도 in-app browser여서 Chrome의 실제 렌더링은 확인하지 못했다. 파일 내용/외부 의존/로그 일치는 검사했으며 화면 확인 성공으로 보고하지 않는다.
