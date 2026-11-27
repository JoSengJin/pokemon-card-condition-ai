# 하네스 6단계 — 채점·승격 판정 도구 (2026-11-27)

```text
task_id: harness-stage6-scoring-promotion-20261127
owner: Claude (구현은 하위 에이전트, 독립 검증은 메인 세션이 별도로 수행)
status: assigned
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

(구현·검증 후 작성)
