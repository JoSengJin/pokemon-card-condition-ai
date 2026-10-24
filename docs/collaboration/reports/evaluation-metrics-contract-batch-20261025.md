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

(단계별 커밋 후 기록한다.)
