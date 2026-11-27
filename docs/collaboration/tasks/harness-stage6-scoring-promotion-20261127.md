# 하네스 6단계 — 채점·승격 판정 도구 (2026-11-27)

```text
task_id: harness-stage6-scoring-promotion-20261127
owner: Claude (구현은 하위 에이전트, 독립 검증은 메인 세션이 별도로 수행)
status: ready_for_review (2차 개정: Opus 독립 검증 반영)
base_sha: d582cc25196dd7b2eb49d55098363a41159979d2 (D-6 승인 기록 커밋 0a4584bb98fd5880ad072bb905018861a590a56d가 그 위에 있음)
branch: claude/harness-scoring-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 6행 "F 채점·승격" 완료 기준을 합성 시험으로 통과한다.
  (a) 판단 보류를 사람 확인 경보로 센 채점(누락률·오탐률·Coverage·층별 보류율·위험-Coverage·분모 0은 "미측정")
  (b) 같은 구역의 두 모델을 실물 카드 단위로 짝지어 부트스트랩한 80% 구간 하한, 라벨 잡음 민감도, 오탐 비열등,
      층별 보류율 상한(D-6)을 모두 만족할 때만 "통과"를 돌려주는 승격 판정
  (c) 보류만 늘린 후보는 탈락하고, 민감도에서 뒤집히는 후보는 승격되지 않으며, 큰 진짜 개선은 통과한다
allowed_files:
  - harness/scoring.py, harness/scoring_rows.py(함수 수 때문에 추가), harness/bootstrap.py, harness/promotion.py,
    harness/promotion_config.py, harness/promotion_reasons.py(2차 개정에서 함수 수 때문에 추가)
  - tests/test_harness_scoring_support.py(시험 공용 도구, 시험 없음),
    tests/test_harness_scoring_counts.py, tests/test_harness_scoring_bootstrap.py, tests/test_harness_scoring_promotion.py,
    tests/test_harness_scoring_gates.py, tests/test_harness_scoring_boundaries.py(2차 개정에서 추가)
  - 이 task 문서
forbidden_files: harness/{cas,ledger,jsonio,contract,manifest,lease,states,queue,graph,checkpoint,recovery,holder,__init__}.py (1단계),
  2단계 runner·7단계 Champion·route() 파일, card_condition/**, tools/**, 기존 tests/**, AGENTS.md,
  artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**
contract:
  입력: 구역 행의 리스트. 행 = dict(id, card_group(실물 카드 그룹), eval_tier(dev|calib|sealed), stratum(비어 있지 않은 문자열), truth(defect|normal|pending),
        pred_a, pred_b(defect|normal|abstain), 선택: score(숫자, 높을수록 확신), uncertain(bool, 불확실 구역))
  출력: JSON으로 직렬화 가능한 dict. 분모가 0인 비율은 숫자 대신 문자열 "미측정".
  호출자·보존: 1단계 파일을 import하거나 호출하지 않는 순수 함수. stdlib만 쓰고(Python 3.9+ 문법) 파일·네트워크·LLM·학습·추론이 없다.
  하지 않는 것: 봉인 평가 실행, 승격 예산·조회 장부, McNemar·순열 검정(확증 단계), Champion 승격, 실제 데이터 읽기.
  규칙(설계 6절 그대로):
    - 오류 판정: 결함 구역에서 pred=normal만 누락, 정상 구역에서 pred=defect 또는 abstain이 오탐(보류=경보).
      pending 구역은 모든 분모에서 제외. 분모 = pending이 아닌 Gold 구역.
    - Coverage = (Gold 구역 − 보류) / Gold 구역. 층별 보류율 = stratum의 보류 / stratum의 Gold 구역.
    - 위험-Coverage 곡선: score 내림차순으로 판정한(보류 아닌) 구역을 누적. 점(threshold, kept, coverage = kept/Gold, risk = 틀린 판정 / kept).
      점수가 없거나 판정한 구역 중 점수가 빠진 구역이 있으면 "미측정". 같은 점수는 한 점으로 묶는다(순서 무관).
      곡선은 보고용이며 보류=경보 집계를 바꾸지 않는다.
    - 보류율 상한(D-6): stratum별 후보 보류율 ≤ min(기준 모델 같은 stratum 보류율 + 0.05, 0.20). 기준 모델 = pred_a, 후보 = pred_b.
      기준 모델이 이미 20%를 넘는 stratum에서는 후보 보류율이 같아도 위반이다(D-6 문구대로).
    - 승격 판정(모두 만족해야 "통과"): (1) 카드 단위 부트스트랩 개선량(A 누락률 − B 누락률)의 10번째 백분위(선형 보간) > 0
      (1a) 결함 구역을 가진 카드 수 ≥ min_defect_cards, 사유 bootstrap_too_few_cards
      (1b) 결함 구역 없는 재표집을 버리고 남은 비율(valid_replicates/replicates) ≥ min_valid_fraction, 사유 bootstrap_too_many_discarded
      (2) 민감도: uncertain 구역의 truth(defect↔normal)를 noise_rate 확률로 독립적으로 뒤집는 trials회 시행 중 개선량 > 0인 비율 ≥ direction_min_fraction.
          uncertain인 Gold 구역이 하나도 없으면 민감도가 평가되지 않은 것이라 사유 sensitivity_vacuous로 미달(보수적).
      (3) 오탐 비열등: 후보 오탐률 − 기준 오탐률 ≤ delta(기본 0.05). 점추정 차이로 판정하며 구간 검정은 6-4 확증 단계 몫이다.
      (4) stratum별 보류율 상한. Coverage는 보고만.
    - noise_rate·direction_min_fraction·min_defect_cards·min_valid_fraction은 기본값이 없는 필수 인자(사전 등록 값). 시험 값은 합성 값이며 권고가 아니다.
      범위: 0<noise_rate<1, 0<direction_min_fraction≤1, 0<min_valid_fraction≤1, min_defect_cards는 1 이상의 int, 0≤delta≤1,
      seed는 int(None·bool 거절), replicates·trials는 1 이상의 int(bool 거절). 어기면 ValueError(필수 인자 누락은 TypeError).
    - 시행 중 최소 개선량은 보고만 하고 판정에 쓰지 않는다(최소 < 0이어도 유지 비율이 기준 이상이면 통과).
    - 보류 몫 분리 보고(improvement_split): 결함 구역 중 'A는 놓쳤는데 B가 보류로 바꾼 구역', 'B가 결함으로 맞힌 구역', 'A는 경보였는데 B가 정상으로 바꾼(악화) 구역'의
      개수·비율과 총 개선 중 보류 몫(abstain_share_of_gross_gain)을 결과에 남긴다. 탈락 사유로 쓰지 않는다(보류 몫을 어떻게 다룰지는 사용자 결정 대기).
    - 호출 계약(필드 의미·값, 2차 개정에서 확정):
        eval_tier = 평가 3층. dev(개발 반복 평가)·calib(라벨 보정 평가)·sealed(봉인 최종 평가). 7단계 Champion의 평가 어휘 `layer == "sealed"`와 같은 값 'sealed'를 쓴다.
        같은 card_group은 eval_tier 사이에 겹칠 수 없다(check_group_overlap, 겹치면 ValueError). evaluate는 eval_tier=="sealed" 행을 ValueError로 거절한다(봉인 행은 확증 단계 몫).
        stratum = D-6 층별 보류율을 나누는 구분(예: 면 앞/뒤, 결함 유형). eval_tier와 독립인 축이며 보류율 상한 검사에만 쓴다.
        구버전 필드 layer는 더 이상 읽지 않는다.
    - 기본 부트스트랩 2000회·민감도 1000회, 난수는 random.Random(seed)(기본 seed=0). 같은 입력·설정은 같은 결과(행 순서 무관).
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩 포함, 람다는 쓰지 않음), 공개 함수 호출 깊이 ≤4(전이 수). 구현 후 ast로 측정해 아래 표를 채운다.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 $MAIN_CHECKOUT/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0
  - 같은 명령을 `/usr/bin/python3`(3.9)로도 실행해 종료 코드 0
  - 1단계 시험 55개 포함 통과, 시험 파일당 테스트 ≤7, 파일당 함수 정의 ≤7($MAIN_CHECKOUT = 기본 checkout 경로. 문서에는 로컬 절대 경로를 적지 않는다)
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
| harness/scoring_rows.py | `validate_rows`(행 형식·eval_tier 값), `check_group_overlap`(eval_tier 사이 카드 중복 → ValueError) |
| harness/scoring.py | `error_kind`, `rate`, `tally`, `report`, `risk_coverage`, `abstain_cap`, `improvement_split` |
| harness/bootstrap.py | `percentile`, `improvement`, `totals`, `paired_bootstrap`, `flip_truths`, `sensitivity` |
| harness/promotion.py | `evaluate`(최종 판정·재현 기록), `_fingerprint` |
| harness/promotion_config.py | `check_config`(사전 등록·실행 값의 형식·범위) |
| harness/promotion_reasons.py | `why`, `bootstrap_reasons`(하한·결함 카드 수·버린 비율·공허한 민감도·방향), `alarm_reasons`(오탐 비열등·보류율 상한) |

## 구조 표 / 인계

### 결과 (1차 구현 + 2차 개정)

필수 시험을 모두 실행해 통과했다. 합성 시험이며 모델 성능·정확도 근거가 아니다. 실험·학습·추론·라벨/사진 읽기·외부 AI 호출은 없다.
실제 데이터에는 적용하지 않았으므로 일반화 개선은 미확인이다.

2차 개정(Opus 독립 검증 '조건부 통과': 차단 1·중요 4·경미 2) 반영 내역:

| 항목 | 처리 |
|---|---|
| 1 차단: 결함 카드 1~2장이면 분산 0 하한으로 통과 | 수정. `min_defect_cards`·`min_valid_fraction` 필수 인자, 사유 `bootstrap_too_few_cards`·`bootstrap_too_many_discarded`. 결함 카드 1·2장 자료가 미달, 경계(같으면 통과) 시험 |
| 2 uncertain 표시 없으면 민감도가 공허한데 통과 | 수정. `n_uncertain==0`이면 `sensitivity_vacuous`로 미달(pending에 붙은 표시는 세지 않음). 0<noise_rate<1, 0<direction_min_fraction≤1 |
| 3 보류로 생긴 개선 몫 | 수정(보고만). `improvement_split`: 보류 몫·정답 몫·악화 구역과 보류 몫 비율. 탈락 사유로 쓰지 않음(사용자 결정 대기) |
| 4 `layer` 이중 의미 | 수정. `eval_tier`(dev/calib/sealed)·`stratum`으로 분리, 카드 중복 검사는 eval_tier, 보류율 상한은 stratum. 탐색 판정은 sealed 행을 ValueError로 거절. 호출 계약을 위 contract에 확정 |
| 5 변이 M02·M03·M06·M08·M11 시험 | 수정. 하한 백분위가 정확히 0.10임을 고정하는 경계 시험(5·10·20번째가 다른 값에 놓이는 자료), 오탐 차이가 정확히 Δ일 때 통과, 분모가 사라진 시행이 섞인 유지 비율, 최악값 < 0이어도 통과하는 시험 |
| 6 설정 검사 | 수정. seed는 int(None·bool 거절), replicates·trials는 bool이 아닌 양의 int, delta는 0 이상 1 이하 |
| 7 문서 | 수정. 아래 "알려진 동작"에 기록, 로컬 절대 경로를 `$MAIN_CHECKOUT` 표기로 교체 |

### 구조 표 (ast로 직접 측정, 람다 없음)

| 파일 | 함수 정의 수(1차 → 2차) | 공개 함수 최대 호출 깊이(전이 수) |
|---|---|---|
| harness/scoring_rows.py | 2 → 2 | `check_group_overlap → validate_rows` 1 |
| harness/scoring.py | 6 → 7 (`improvement_split` 추가) | `report → tally → error_kind` 2 |
| harness/bootstrap.py | 6 → 6 | `paired_bootstrap → totals → error_kind` 2 |
| harness/promotion.py | 5 → 2 (`evaluate`, `_fingerprint`) | `evaluate → sensitivity → totals → error_kind` 3 |
| harness/promotion_config.py (신규) | 0 → 1 | 0 |
| harness/promotion_reasons.py (신규) | 0 → 3 | `bootstrap_reasons → why` 1 |
| tests support / counts / bootstrap / promotion / gates / boundaries | 6 / 7 / 7 / 7 / 4 / 4 (시험은 0 / 7 / 7 / 7 / 4 / 4) | — |

최대 호출 깊이 3(한도 4). 이름 기반 정적 분석(저장소 밖 `struct6.py`)이며 동적 디스패치·콜백·재귀 없음. 1단계 파일은 import·호출하지 않는다.

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 1차: 작업 계약 / 구현 / 시험 / 인계 문서 | `c9d8aa4` / `adef0cee3141a013bd3a2351e4347691cbed6100` / `b648dd80b2382d29ecf4e7485a91eaac51d5aac4` / `8f7aeb4317494ea36643ffb62b09b3eb659225b3` |
| 2차 구현(`feat(harness)`) | `d55c0fab1e05d1330f1a8a72e26c97a7f30f4cf9` |
| **2차 시험 대상(구현 + 시험, `test(harness)`)** | `92a184e334b374c6c1cbbea794ab32aee882cc6e` |
| 이 문서 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음). SHA는 `git log`로 확인 |

2차 시험 커밋 메시지의 "31개"는 오기이며 실제 6단계 시험은 29개다(counts 7·bootstrap 7·promotion 7·gates 4·boundaries 4). 이력 재작성은 하지 않았다.

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 $MAIN_CHECKOUT/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py" > /tmp/out6.txt 2>&1` (Python 3.12.14) | 0 (84개 통과 = 1단계 55 + 6단계 29) |
| `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -p "test_harness_*.py" > /tmp/out6b.txt 2>&1` (Python 3.9.6) | 0 (84개 통과) |
| 변이 확인 `mutate7.py`(저장소 밖, 임시 복사본에서만 변경): 무변이 대조 + 54개 변이(1차 16 + 검증자 V01~V22 + 신규 N1~N8 등), Python 3.12 | 무변이 rc=0, 변이는 모두 rc=1(살아남은 변이 0) |
| 같은 변이 확인, Python 3.9 | 무변이 rc=0, 변이는 모두 rc=1(살아남은 변이 0) |
| `git diff --check` | 0 |
| `git diff --name-only 8f7aeb4 HEAD` | 허용 파일만(harness 6개·tests 6개·이 문서) |

변이 중 처음 살아남아 시험을 보강한 것: V16(기준에 없는 stratum은 미측정, `abstain_cap` 직접 시험), V21(민감도가 보고한 seed 그대로 난수를 쓰는지 1시행 손 재현), N6c(delta=1 경계 허용).
시험은 약화하지 않았다. 검증자 스크립트(`adversarial*.py`)는 옛 `layer` 필드·옛 인자를 써서 그대로 실행되지 않으므로 같은 시나리오를 시험으로 옮겼다(2a~2c → gates 1, 3a → gates 3, adversarial2 보류만 늘림 → boundaries 4).

### 1종 오류 재확인 (검증자 `sim.py`, 카드 수준 부트스트랩 하한 단독)

150회·재표집 500회로 다시 돌렸다(저장소 밖). 참 개선 0일 때 P(하한 > 0)은 5~15%로 단측 10% 수준에 가깝고(카드 5장 0.153, 15장 0.087, 40장 0.073, 120장 0.133 — 150회라 ±3%p 흔들림),
`paired_bootstrap`의 점추정·하한 계산은 2차 개정에서 바뀌지 않았다. 이 시뮬레이션은 부트스트랩 하한 단독의 1종 오류이며 `evaluate` 전체(민감도·오탐·상한·카드 수 관문 포함)의 1종 오류가 아니다. 전체 1종 오류는 측정하지 않았다.

### 알려진 동작과 한계

- 기준 모델이 이미 20%를 넘는 stratum에서는 후보 보류율이 같아도 위반이다(D-6 문구 "절대 상한 20%"대로).
- 오탐 비열등은 점추정 차이(후보 − 기준 ≤ Δ)로 판정한다. 구간 기반 비열등 검정은 6-4 확증 단계 몫이다.
- 민감도 뒤집기는 구역마다 독립이며 같은 카드 안 라벨 잡음의 상관은 모사하지 않는다. 같은 카드의 구역이 함께 틀릴 때는 실제 불안정이 더 크다.
- 보류로 생긴 개선도 현재는 판정에서 막지 않는다(D-6 안에서 보류를 늘려 누락을 줄인 후보가 통과할 수 있음). `improvement_split`으로 몫만 보고한다. 사용자 결정 대기.
- 부트스트랩 하한은 10번째 백분위(선형 보간). 결함 구역 없는 재표집은 건너뛰고 `min_valid_fraction`으로 상한을 둔다. 민감도에서 결함 구역이 사라진 시행은 유지 못 한 것으로 센다.
- `min_defect_cards`·`min_valid_fraction`·`noise_rate`·`direction_min_fraction` 값은 코드가 정하지 않는다. 시험의 값(5~10, 0.9, 0.1 등)은 합성 값이며 권고가 아니다.
- 위험-Coverage의 `score`는 "높을수록 판정을 확신"으로 읽었다. 곡선은 보고용이다.
- 기본 `seed=0`은 편의값이다. 부트스트랩과 민감도가 같은 seed로 각자 독립 `random.Random`을 만든다.

### 미검증

- 실제 데이터·실제 모델 출력, 실제 카드 수·잡음률에서의 검정력, 수천 카드·수만 행 규모의 실행 시간.
- `evaluate` 전체(모든 관문 결합)의 1종 오류율과 검정력.
- 확증 단계(McNemar·순열, 봉인 평가 1회, 승격 예산·조회 장부)와 Champion 연결. 이 단계는 호출되지 않는다.
- 7단계 Champion과의 `sealed` 어휘 일치는 문서상 약속이며 7단계 코드와 대조하지 않았다(다른 worktree를 읽지 않음).
- 2차 개정 후 독립 재검증(Opus)은 하지 않았다(메인 세션 몫).

### 리스크

- 호출자가 `eval_tier`와 `stratum`을 계약과 다르게 채우면 정상 입력을 오류로 거절하거나(같은 카드가 eval_tier에 걸침) 상한이 의도와 다르게 적용될 수 있다.
- 사전 등록 값을 시험 값으로 복사해 쓰면 기준이 부적절할 수 있다.
- 보류 몫이 큰 후보가 현재는 통과할 수 있다(위 한계).
- 호출 인자(`min_defect_cards`, `min_valid_fraction`)가 늘어 `evaluate`의 호출자가 모두 갱신돼야 한다(현재 호출자는 시험뿐).

### 롤백

- 2차 개정만 되돌리려면 2차 `docs`/`test`/`feat` 커밋 3개를 역순으로 `git revert`한다. 6단계 전체는 1차 포함 커밋을 역순으로 `git revert`(새 파일만 추가했으므로 다른 파일 영향 없음).
- 1단계·2단계 파일은 변경하지 않았다. 통합 전이므로 main·push 변경 없음.

### 성과·진척 HTML

모델 성능을 새로 평가하거나 비교하지 않았고 정확도·진척률 보고 대상이 아니다(합성 시험만). HTML 산출물은 만들지 않았다(해당 없음, 이유: 실제 사진·구역·모델 출력이 없음).

### 적용 스킬·품질 규칙

- 스킬: verification-before-completion(명령·종료 코드·SHA 대조). TDD·리뷰 스킬은 쓰지 않음.
- 품질 규칙: `zero-denominator-unmeasured`(분모 0은 "미측정", 통과로 세지 않음), `chance-check`(시드·반복 시행 표기, 같은 자료 반복 통과는 개선 근거가 아님), `regression-for-every-fix`(검증자 지적·살아남은 변이마다 시험 보강).
  `can-this-experiment-tell`은 실험 계획이 아니어서 해당 없음.
