# Claude 평가 수치 계약·반례 검증 묶음

- task_id: evaluation-metrics-contract-batch-20261025
- owner: Claude
- status: integrated
- base_sha: aa3e74583f8d2213b9dbad8f664c0a1ce0f8f703
- branch: claude/evaluation-metrics-contract-batch-20261025
- worktree/dispatch: Codex 전달 메시지 참조

## 목표와 범위

고정된 합성 정답·이미 계산된 확률만 사용해 누락/오탐 분모, paired 비교 대상 동일성, 순위 지표, 보류와 실물별 집계가 거짓 개선 결론을 만들지 않는지 검증한다. 모델 실행이나 새 평가 도구를 만드는 작업이 아니다. 기존 동작이 맞으면 반례·회귀 검사만 남긴다. 실제 결함이 재현된 경우만 허용된 세 소스에 최소 수정한다. Mastra와 snapshot/sidecar 도구에는 손대지 않는다.

## allowed_files (10개, HTML 보완 계약 포함)

- card_condition/quality_rates.py (기존: 함수 정의 2개)
- card_condition/regression_audit.py (기존: 중첩 포함 함수 정의 3개)
- card_condition/score_diagnostics.py (기존: 함수 정의 2개)
- tests/test_metric_denominator_contract.py (신규)
- tests/test_paired_population_contract.py (신규)
- tests/test_ranking_abstention_contract.py (신규)
- tests/test_metric_metamorphic_contract.py (신규)
- docs/collaboration/tasks/evaluation-metrics-contract-batch-20261025.md
- docs/collaboration/reports/evaluation-metrics-contract-batch-20261025.md (신규)
- docs/collaboration/reports/evaluation-metrics-contract-batch-20261025.html (Codex HTML 보완)

기존 tests/test_quality_rates.py,test_regression_audit.py,test_score_diagnostics.py 및 모든 호출자는 읽기 전용이다. 추가 소스 파일·추상화·새 지표/기준·경로 탐색·HTML/UI·실험 실행기는 만들지 않는다. 호출자에서 해결해야 하는 문제면 정확한 재현과 수정 제안만 기록해 Codex에 인계한다.

## 현재 공용 지침 보존과 구조 계약

배정 시 main의 AGENTS.md와 PAIR_CODING.md에는 사용자 변경이 미커밋 상태다. Codex는 이를 커밋·stash·되돌리지 않는다. 새 worktree는 위 base의 커밋된 코드에서 출발하며 최신 구조 제한은 이 계약으로 명시한다.

수정 파일은 함수 정의 최대7개(일반/비동기/메서드/중첩 합계), 주요 호출 경로 전이 최대4회를 따른다. 테스트도 정의 수를 기록하고 매개변수화/subTest로 의미 있는 독립 사례를 묶되 한 함수에 다른 책임을 억지로 합치지 않는다. 기존 파일을 추가 분리하거나 함수 래퍼를 만들어 깊이를 감추지 않는다. 전/후 함수 개수·파일을 넘는 주요 호출 경로를 보고서에 기록한다. 정적으로 미확인인 호출/순환은 통과로 간주하지 말고 기록한다. 제한 때문에 필요한 변경이 불가능하면 실패 재현을 보존하고 해당 수정만 보류한다.

## 1. 입력 경계와 손계산 기준 고정

세 소스와 실제 호출자/기존 검사를 읽고 어떤 입력이 upstream에서 검증되는지 먼저 명시한다. 불가능한 입력을 근거로 leaf 함수에 중복 검증을 붙이지 않는다. 전제된 입력과 실제 지원 입력의 오류 처리를 구별한다. 오류 종류나 출력 schema를 임의로 바꾸지 않는다.

기존 수치 계약: threshold=0.5, FN/(TP+FN), FP/(TN+FP), 변화는 같은 분모에서 candidate-reference의 %p. 양성/정상 분모0은 None이며 0%로 보고하지 않는다. 미확인 truth=None은 정상0이 아니다. 보류된 정답 행은 원래 raw 평가 분모와 구별한다. 보류 수용 분모로 계산한 risk를 원래 누락률로 보고하지 않는다.

fixture의 기대값은 손계산 표·작은 정수 비율·독립 pairwise 순위 계산으로 정한다. 구현 함수를 다시 호출해 기대값을 만드는 검사는 피한다. 실제 모델 성능·정확도·진척률은 갱신하지 않는다.

## 2. 분모와 paired 대상 동일성

- 빈/한 종류만 있는 confusion counts, 정상/결함 각각의 분모, 두 종류 동시 개선/악화, accuracy만 좋아진 경우를 검사한다.
- 집계 FN/FP가 줄어도 새 누락/새 오탐이 생기면 no_new_errors가 false인지 검사한다. aggregate_improved와 informative_improvement의 의미를 구분한다.
- 같은 행의 순서만 바꿔도 ID로 정렬된 결과는 동일해야 한다. 누락/추가 ID, 중복 ID, 같은 ID의 다른 group/side/split/image_sha256/card_box/box/정답은 paired 비교에서 거절돼야 한다.
- 새 unknown 라벨을 정상으로 끼워 넣거나 다른 cohort의 같은 길이 점수를 개선으로 비교하지 않는다. compare_runs의 실제 field 계약을 따르고 사진/실물 분리가 증명됐다고 확대 해석하지 않는다.
- 실패·올바른 거절·유효 입력 통과를 각각 검사한다. 현 API가 지원하지 않는 불완전한 레코드는 호출자 전제와 함께 기록한다.

## 3. 순위 지표와 보류 경계

- 양성/음성 각1~3개 합성 점수에 AUROC를 모든 양성-음성 쌍의 승리1/동점0.5로 독립 계산해 대조한다.
- 완전 분리/완전 역순/동점/일부 동점/행 순서 변화의 AUROC와 AP 기대값을 손계산으로 고정한다. AP는 동점 묶음 처리 규칙을 기존 계약과 맞춰 명시한다. 한 종류만 있는 자료의 None 처리도 확인한다.
- 각 고정 low/high에서 value<low, low<=value<high, value>=high를 검사한다. .5/.5에서는 raw0.5 판정과 일치해야 한다.
- unknown 행은 known 분모에 들어가지 않고, known이 모두 보류된 실물도 by_group와 zero_accepted_known_groups에 남아야 한다.
- micro risk, 실물별 risk 평균, accepted_groups의 분모를 구분한다. 한 실물의 구역이 많아 생기는 가중 차이를 버그로 단정하지 않는다.

## 4. 작고 결정적인 전수·변환 검사

확률 몇 개와 최대4행의 작은 조합만 사용한다. 고정 seed 또는 명시 리스트로 재현 가능하게 하고 시간 예산을 기록한다. 무작위 대량 fuzz·새 라이브러리는 금지한다.

행 순열에서 집계·순위 불변, cohort를 그대로 복제했을 때 비율 불변/개수2배, before/after 동일 시 새 오류0/%p0, threshold 경계 이동 시 예상되는 confusion 전이 등을 검사한다. 복제 검사는 순수 집계 함수에만 적용하며 compare_runs의 중복 ID 거절과 섞지 않는다. 같은 입력 반복으로 테스트 수만 늘리지 않는다.

## 5. 재현된 결함만 최소 보완

실제 호출 가능한 경로의 결함은 먼저 실패 검사와 손계산 기대값을 커밋하고 세 소스 안에서 최소 수정한다. 스펙이 모호하거나 모델/사람 판단이 필요한 내용은 정답을 만들어 고치지 않는다. 유효 입력 출력 계약을 바꿔야 하면 그 부분을 보류하고 이유·최소 제안을 남긴다. 의미 없는 방어 코드·성능 최적화·공용 리팩터링 없음.

주요 분기의 작은 mutation 대조는 임시 복사본에서 선택적으로 수행한다. branch/파일 변경은 현재 worktree에만 하고 실패 검사·수정·재실행을 구분한다.

## 6. 전체 검사와 인계

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_quality_rates test_regression_audit test_score_diagnostics test_metric_denominator_contract test_paired_population_contract test_ranking_abstention_contract test_metric_metamorphic_contract -v
.venv/bin/python -m compileall -q card_condition/quality_rates.py card_condition/regression_audit.py card_condition/score_diagnostics.py
git diff --check
```

표준 라이브러리 자체 .venv만 사용한다. 세 대상 모듈은 torch/Pillow 없이 import 가능하다. 다른 venv·모델·사진·데이터·snapshot 복사 없음. 카드 모델 source 편집은 ./develop -- <실제 수정 명령> 안에서 수행한다. 기존 ML 의존 통합 검사는 Codex가 수행한다.

보고서에 손계산 표·테스트 이름 대응·실패 재현과 수정 SHA·실행 명령/개수·구조 제한·리스크·미검증을 적는다. status ready_for_review, 전체 커밋 순서/부모/허용 파일 대조/깨끗한 작업 트리로 인계한다. test 실패가 없는 것도 유효한 결과이며 수정량·테스트 수 목표를 채우지 않는다.

## 금지·종료·롤백

모델 학습·추론·실제 평가·외부 AI/Codex CLI/review --auto·test split 실자료 열람·사람 라벨 변경·Mastra 작업·main merge/push 금지. 기존 30/100과 배점·품질기준 불변. 의미 결정을 요구하는 항목만 보류하고 남은 독립 단계를 계속한다. 6단계 완료 또는 실제 권한/컨텍스트 한계에서 체크포인트를 남긴다. 롤백은 미통합 또는 전달 커밋 역순 revert이며 모델·라벨 복구가 필요 없어야 한다.

## Claude 실행 결과

2026-10-25, 배정 worktree에서 실행. 상세: `docs/collaboration/reports/evaluation-metrics-contract-batch-20261025.md`.

- 기준:
  - 브랜치 `claude/evaluation-metrics-contract-batch-20261025`, 시작 HEAD `024e64fad3bc397eeae80a294f2d63a916e78a57`.
  - `merge-base --is-ancestor aa3e745… HEAD` 종료코드 0.
  - base 이후 Codex 변경은 prompt·task 문서뿐이었다.
- 커밋 순서:
  1. `383d13dfa1484a7dad2168e73687ce10a041362e` docs: 입력 경계·손계산·구조
  2. `247b7a9662c686784a5375044b54313cf3900415` test: 분모·paired
  3. `66b2c3e8abbb89428d24c9748ed72f2331a216df` test: 순위·보류
  4. `65c394c227877ff2a18c94988f3e93575af47a21` test: 전수·변환
  5. `085a498c08aba52504fa9fd454a45b5cc0aa881f` test: 실물별 경계 대조 보강
  6. 이 문서 커밋
- 결론: 재현된 소스 결함 없음. 세 소스 diff 0, 회귀 검사만 추가했다.
- 검사:
  - 지정 명령 → 34개 통과(기존 13, 신규 21), 종료코드 0.
  - `compileall` 0, `git diff --check` 통과.
  - 작은 전수 1,818개 cohort, 약 0.2초.
  - mutation 13개 중 12개가 처음부터 검출됐다. 나머지 1개는 검사 빈틈이었고, 보강한 뒤 검출된다.
- 구조 제한: 소스 함수 수 2/3/2(전후 동일), 신규 테스트 5/7/7/6. 최대 호출 전이는 소스 2, 테스트 경로 3.
- 미검증:
  - 기존 ML 의존 통합 검사(Codex 몫)
  - upstream 전제 밖 입력(NaN 확률·필드 누락·혼합 ID 타입): 오류 종류를 바꾸지 않고 전제로 기록
- 리스크: 합성 검증이며 실제 성능을 말하지 않는다. AP는 비보간·동점 묶음 정의다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 역순으로 revert한다. 모델·라벨 복구는 필요 없고 진척률 30/100은 그대로다.


## Codex 인수

부모/파일 범위와 깨끗한 worktree 확인 후6커밋을 main에 통합했다. 기본 환경177 tests 통과, source 세 파일 diff0, 신규 테스트 정의 수5/7/7/6을 재검증했다. Codex가 HTML 보완 계약에 따라 성과·고정 진척 보고서를 추가했다. 실제 모델 성능 미평가·진척30/100 유지. 상세는 보고서 Codex 절과 artifacts/evaluation-metrics-integration-20261025/를 참조한다.
