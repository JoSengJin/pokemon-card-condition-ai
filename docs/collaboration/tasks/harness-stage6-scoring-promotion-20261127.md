# 하네스 6단계 — 채점·승격 판정 도구 (2026-11-27)

```text
task_id: harness-stage6-scoring-promotion-20261127
owner: Claude (구현은 하위 에이전트, 독립 검증은 메인 세션이 별도로 수행)
status: ready_for_review
base_sha: d582cc25196dd7b2eb49d55098363a41159979d2 (D-6 승인 기록 커밋 0a4584bb98fd5880ad072bb905018861a590a56d가 그 위에 있음)
branch: claude/harness-scoring-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 6행 "F 채점·승격" 완료 기준을 합성 시험으로 통과한다.
  (a) 판단 보류를 사람 확인 경보로 센 채점(누락률·오탐률·Coverage·층별 보류율·위험-Coverage·분모 0은 "미측정")
  (b) 같은 구역의 두 모델을 실물 카드 단위로 짝지어 부트스트랩한 80% 구간 하한, 라벨 잡음 민감도, 오탐 비열등,
      층별 보류율 상한(D-6)을 모두 만족할 때만 "통과"를 돌려주는 승격 판정
  (c) 보류만 늘린 후보는 탈락하고, 민감도에서 뒤집히는 후보는 승격되지 않으며, 큰 진짜 개선은 통과한다
allowed_files:
  - harness/scoring.py, harness/scoring_rows.py(함수 수 때문에 추가), harness/bootstrap.py, harness/promotion.py
  - tests/test_harness_scoring_support.py(시험 공용 도구, 시험 없음),
    tests/test_harness_scoring_counts.py, tests/test_harness_scoring_bootstrap.py, tests/test_harness_scoring_promotion.py
  - 이 task 문서
forbidden_files: harness/{cas,ledger,jsonio,contract,manifest,lease,states,queue,graph,checkpoint,recovery,holder,__init__}.py (1단계),
  2단계 runner·7단계 Champion·route() 파일, card_condition/**, tools/**, 기존 tests/**, AGENTS.md,
  artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**
contract:
  입력: 구역 행의 리스트. 행 = dict(id, card_group(실물 카드 그룹), layer, truth(defect|normal|pending),
        pred_a, pred_b(defect|normal|abstain), 선택: score(숫자, 높을수록 확신), uncertain(bool, 불확실 구역))
  출력: JSON으로 직렬화 가능한 dict. 분모가 0인 비율은 숫자 대신 문자열 "미측정".
  호출자·보존: 1단계 파일을 import하거나 호출하지 않는 순수 함수. stdlib만 쓰고(Python 3.9+ 문법) 파일·네트워크·LLM·학습·추론이 없다.
  하지 않는 것: 봉인 평가 실행, 승격 예산·조회 장부, McNemar·순열 검정(확증 단계), Champion 승격, 실제 데이터 읽기.
  규칙(설계 6절 그대로):
    - 오류 판정: 결함 구역에서 pred=normal만 누락, 정상 구역에서 pred=defect 또는 abstain이 오탐(보류=경보).
      pending 구역은 모든 분모에서 제외. 분모 = pending이 아닌 Gold 구역.
    - Coverage = (Gold 구역 − 보류) / Gold 구역. 층별 보류율 = 층의 보류 / 층의 Gold 구역.
    - 위험-Coverage 곡선: score 내림차순으로 판정한(보류 아닌) 구역을 누적. 점(threshold, kept, coverage = kept/Gold, risk = 틀린 판정 / kept).
      점수가 없거나 판정한 구역 중 점수가 빠진 구역이 있으면 "미측정". 같은 점수는 한 점으로 묶는다(순서 무관).
      곡선은 보고용이며 보류=경보 집계를 바꾸지 않는다.
    - 보류율 상한(D-6): 층별 후보 보류율 ≤ min(기준 모델 같은 층 보류율 + 0.05, 0.20). 기준 모델 = pred_a, 후보 = pred_b.
    - 승격 판정(모두 만족해야 "통과"): (1) 카드 단위 부트스트랩 개선량(A 누락률 − B 누락률)의 10번째 백분위(선형 보간) > 0
      (2) 민감도: uncertain 구역의 truth(defect↔normal)를 noise_rate 확률로 독립적으로 뒤집는 trials회 시행 중 개선량 > 0인 비율 ≥ direction_min_fraction
      (3) 오탐 비열등: 후보 오탐률 − 기준 오탐률 ≤ delta(기본 0.05) (4) 층별 보류율 상한. Coverage는 보고만.
    - direction_min_fraction과 noise_rate는 기본값이 없는 필수 인자(사전 등록 값). 시험 값은 합성 값이며 권고가 아니다.
    - 시행 중 최소 개선량은 보고만 하고 판정에 쓰지 않는다. 같은 구역 모두에서 판정 시 층 사이 같은 카드 그룹이 있으면 ValueError.
    - 기본 부트스트랩 2000회·민감도 1000회, 난수는 random.Random(seed)(기본 seed=0). 같은 입력·설정은 같은 결과(행 순서 무관).
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩 포함, 람다는 쓰지 않음), 공개 함수 호출 깊이 ≤4(전이 수). 구현 후 ast로 측정해 아래 표를 채운다.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0
  - 같은 명령을 `/usr/bin/python3`(3.9)로도 실행해 종료 코드 0
  - 1단계 시험 55개 포함 통과, 시험 파일당 테스트 ≤7
  - 변이 확인(임시 복사본에서): 보류 처리 규칙 변경, 카드 단위 재표집 → 구역 단위, 민감도 판정 제거, 상한 검사 제거가 시험에 잡힘
  - `git diff --check`, `git diff --name-only d582cc2 HEAD`가 허용 파일 안인지, `git status` 깨끗
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다. ./experiment·학습·추론·라벨 읽기·외부 AI 호출 없음.
handoff: 아래 "구조 표 / 인계" 절(구현 후 작성).
```

## 설계 근거(원문)

- DESIGN.md 2절 원칙 3(판단 보류 = 경보), 6-1(분모와 판단 보류), 6-3(탐색 → 확증 승격 조건 3가지), 6-5(같은 실물 카드는 층 사이 겹치지 않음).
- DECISIONS.md D-6(보류율 상한: 층별 현재값 +5%p 이내, 절대 상한 20%), IMPLEMENTATION.md 2절 6행.
- `tools/diagnostics/ab-sample-size-20261124/size.py`는 확증 단계의 장수 산정 도구이며 이 단계에서는 호출·수정하지 않는다.

## 파일 구성

| 파일 | 책임 |
|---|---|
| harness/scoring_rows.py | `validate_rows`(행 형식), `check_group_overlap`(층 사이 카드 중복 → ValueError) |
| harness/scoring.py | `error_kind`, `rate`, `tally`, `report`, `risk_coverage`, `abstain_cap` |
| harness/bootstrap.py | `percentile`, `improvement`, `totals`, `paired_bootstrap`, `flip_truths`, `sensitivity` |
| harness/promotion.py | `evaluate`(최종 판정·재현 기록), 보조 `_check_config`, `_reasons`, `_why`, `_fingerprint` |

## 구조 표 / 인계

### 결과

필수 시험을 모두 실행해 통과했다. 합성 시험이며 모델 성능·정확도 근거가 아니다. 개발 진척 단계 6(채점·승격 판정 도구)의 구현이고
실험·학습·추론·라벨/사진 읽기·외부 AI 호출은 없다. 도구는 구현·시험까지이며 실제 데이터에 적용하지 않았다(독립 평가가 없으므로 일반화 개선은 미확인).

### 구조 표 (ast로 직접 측정, 람다 없음)

| 파일 | 함수 정의 수(전 → 후) | 공개 함수 최대 호출 깊이(전이 수) |
|---|---|---|
| harness/scoring_rows.py (신규) | 0 → 2 (`validate_rows`, `check_group_overlap`) | `check_group_overlap → validate_rows` 1 |
| harness/scoring.py (신규) | 0 → 6 (`error_kind`, `rate`, `tally`, `risk_coverage`, `report`, `abstain_cap`) | `report → tally → error_kind` 2 |
| harness/bootstrap.py (신규) | 0 → 6 (`percentile`, `improvement`, `totals`, `paired_bootstrap`, `flip_truths`, `sensitivity`) | `paired_bootstrap → totals → error_kind` 2 |
| harness/promotion.py (신규) | 0 → 5 (`_why`, `_check_config`, `_fingerprint`, `_reasons`, `evaluate`) | `evaluate → paired_bootstrap → totals → error_kind` 3 |
| tests/test_harness_scoring_support.py (신규, 시험 없음) | 0 → 7 | — |
| tests/test_harness_scoring_counts.py / _bootstrap.py / _promotion.py (신규) | 각 7 (모두 시험, 보조 함수 없음) | — |

주요 호출 경로 최대 3회(한도 4). 호출 대상은 이름 기반 정적 분석(`struct6` 스크립트, 저장소 밖)으로 확정했고 동적 디스패치·콜백·재귀 없음. 1단계 파일은 import·호출하지 않는다.

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 작업 계약 커밋 | `c9d8aa4` (전체 SHA는 `git log`) |
| 구현(`feat(harness)`) | `adef0cee3141a013bd3a2351e4347691cbed6100` |
| 시험 대상(구현 + 시험, `test(harness)`) | `b648dd80b2382d29ecf4e7485a91eaac51d5aac4` |
| 이 문서 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음). SHA는 `git log`로 확인 |

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14) | 0 (76개 통과 = 1단계 55 + 6단계 21) |
| `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.9.6) | 0 (76개 통과) |
| 변이 확인 `mutate6.py`(저장소 밖, 임시 복사본에서만 변경) 16개 변이 + 무변이 대조, 두 Python 모두 | 무변이 rc=0, 변이 16개 모두 rc=1(시험이 잡음) |
| `git diff --check` | 0 |
| `git diff --name-only d582cc2 HEAD` | 허용 파일 + D-6 승인 커밋 0a4584b의 DECISIONS.md(이 작업의 변경이 아님) |

변이 16개와 잡은 시험(요약): 정상 구역 보류를 오탐으로 안 셈, 결함 구역 보류를 누락으로 셈, Coverage 분모 변경(보류 제외), 카드 단위 → 구역 단위 재표집, 민감도 판정 제거,
보류율 상한 검사 제거, 상대 +5%p 제거, 오탐 비열등 제거, 하한 백분위 10 → 50, 하한 > 0 검사 제거, pending을 Gold에 포함, 부트스트랩 시드 제거, 민감도 시드 제거,
민감도 `> 0` → `>= 0`, 뒤집기가 uncertain 무시, 층 중복 검사 제거. 처음에는 하한 백분위·하한 > 0 제거·시드 제거·`>= 0` 4개가 살아남아 시험을 보강했다(3 카드 판정 시험,
카드당 구역 수가 다른 자료의 시드 시험, 개선량 0 시험). 시험은 약화하지 않았다.

### 필수 시험 대응

| 필수 | 시험 |
|---|---|
| 보류만 늘린 후보 탈락(정상 구역 전부 보류 / 결함 구역만 보류) | promotion :: test_abstaining_on_every_normal_zone_is_rejected_by_false_alarm_and_cap, test_abstaining_only_on_defect_zones_to_cut_misses_is_rejected_by_abstain_cap_alone |
| 민감도에서 뒤집히는 후보는 승격 안 됨(통제 비교 포함) | promotion :: test_small_gain_that_label_noise_erases_is_not_promoted |
| 큰 진짜 개선 통과 | promotion :: test_large_genuine_improvement_with_enough_cards_passes_but_not_on_three_cards |
| 카드 단위 재표집 효과(카드 수가 적으면 구간이 넓어짐) | bootstrap :: test_resampling_unit_is_the_card_not_the_zone, test_fewer_cards_widen_the_interval_for_the_same_pooled_rates |
| 분모 0은 미측정이며 통과가 아님 | counts :: test_pending_is_outside_every_denominator_and_zero_denominator_is_unmeasured, bootstrap :: test_no_defect_rows_is_unmeasured_not_zero, promotion :: test_zero_denominators_are_unmeasured_and_never_pass |
| 같은 시드 같은 결과, 다른 시드에서 크게 달라지지 않음 | bootstrap :: test_same_seed_same_result_row_order_irrelevant_other_seeds_close_but_not_identical, promotion :: test_result_records_inputs_config_and_seed_and_is_reproducible |
| 층 사이 카드 중복 검사 | counts :: test_group_overlap_across_layers_is_an_error_and_bad_rows_are_rejected, promotion :: test_inputs_are_validated_and_preregistered_values_are_required |

### 추가한 점검

- 점추정이 커도 카드 수가 3장이면 "미달"(`bootstrap_lower_not_positive`): 같은 구역을 독립으로 센 착시를 막는다.
- 개선량 0은 방향 유지로 세지 않는다(`> 0`). 민감도에서 분모가 사라진 시행은 유지 못 한 것으로 센다(보수적).
- 두 사전 등록 값(`noise_rate`, `direction_min_fraction`)이 없으면 `TypeError`, 범위 밖이면 `ValueError`.
- 결과 dict에 행 sha256(id 정렬, 행 순서 무관)·설정·시드·카드 수를 함께 남긴다. 행 자체는 저장하지 않으므로 호출자가 같은 행을 보관해야 재현된다.

### 가정

- 설계의 "층"을 행의 `layer` 하나로 읽었다. 층별 보류율(D-6)과 층 사이 카드 중복 검사(6-5)가 같은 필드를 쓴다. 평가 3층(개발·보정·봉인)이 아니라
  앞/뒷면 같은 다른 구분을 `layer`에 넣고 같은 카드가 두 값에 걸치면 `evaluate`가 ValueError를 낸다. 확정 전 호출 계약에서 `layer` 의미를 정해야 한다.
- 위험-Coverage의 `score`는 "높을수록 판정을 확신한다"로 읽었다. 점수 정의가 다르면 해석이 달라진다. 곡선은 보고용이다.
- 민감도 뒤집기는 uncertain 구역마다 독립 베르누이(noise_rate)다. 같은 카드 구역끼리의 상관은 모사하지 않는다. "최악의 경우 값"은 이론상 최악이 아니라
  시행 중 최소 개선량(`min_improvement`)이며 판정에 쓰지 않는다.
- 80% 구간의 하한 = 10번째 백분위(선형 보간). 결함 구역이 없는 부트스트랩 표본은 값이 정의되지 않아 건너뛰고 `valid_replicates`에 남긴다(건너뛴 비율에 대한 기준은 없음).
- 오탐 비열등·보류율 상한의 경계는 `<=`이며 부동소수점 오차 1e-12를 허용한다. 보류율 상한 비교 대상(기준 모델)은 `pred_a`다.
- 부트스트랩과 민감도가 같은 `seed`로 각자 독립 `random.Random`을 만든다. 기본 `seed=0`은 편의값이며 사전 등록 값으로 쓰려면 호출자가 명시한다.

### 미검증

- 실제 데이터·실제 모델 출력에 대한 동작, 실제 카드 수·잡음률에서의 검정력과 민감도(합성 값뿐).
- 확증 단계(McNemar·순열, 봉인 평가 1회, 승격 예산·조회 장부)와 Champion 승격과의 연결. 이 단계는 호출되지 않는다.
- 성능 단위 시간: 2000회 부트스트랩 + 1000회 민감도는 합성 400행에서 0.1초 이하. 수천 카드·수만 행 규모는 측정하지 않았다.
- 독립 검증(Opus)은 하지 않았다(메인 세션이 별도로 수행).

### 리스크

- `layer` 의미를 잘못 잡으면 정상 입력을 오류로 거절하거나(위 가정) 층별 상한이 의도와 다르게 적용될 수 있다.
- 사전 등록 값을 코드가 정하지 않으므로, 호출자가 시험용 값(0.1/0.9 등)을 그대로 복사해 쓰면 판정 기준이 부적절할 수 있다. 시험 값은 권고가 아니다.
- 카드 수가 매우 적으면 결함 구역이 없는 표본이 많아져 하한 계산이 편향될 수 있다(건너뛴 표본 수 확인 필요).

### 롤백

- 이 작업의 `docs`/`test`/`feat` 커밋을 역순으로 `git revert`한다(새 파일만 추가했으므로 다른 파일 영향 없음). 1단계·2단계 파일은 변경하지 않았다.
- worktree 전달은 커밋 SHA 기준이다. 통합 전이므로 main·push 변경 없음.

### 성과·진척 HTML

모델 성능을 새로 평가하거나 비교하지 않았고 정확도·진척률 보고 대상이 아니다(합성 시험만). HTML 산출물은 만들지 않았다(해당 없음, 이유: 실제 사진·구역·모델 출력이 없음).

### 적용 스킬·품질 규칙

- 스킬: verification-before-completion(명령·종료 코드·SHA 대조). TDD·리뷰 스킬은 쓰지 않음.
- 품질 규칙: `zero-denominator-unmeasured`(분모 0은 "미측정", 통과로 세지 않음), `chance-check`(시드·반복 시행 표기, 같은 자료 반복 통과는 개선 근거가 아님), `regression-for-every-fix`(살아남은 변이마다 시험 보강).
  `can-this-experiment-tell`은 실험 계획이 아니어서 해당 없음.
