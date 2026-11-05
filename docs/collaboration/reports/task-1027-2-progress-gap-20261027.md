# task-1027-2 진척 공백 분석 — 2026-10-27

개발 진척률 **30/100 (usable-card-analysis-v1.0, 직전 동일기준 대비 +0%p)**. 이번 성과: 소스 변경 0, 진척 차단 요인과 다음 task 2개를 코드 근거로 정리했다. 모델 성능 변화는 측정하지 않았다.

- 기준 SHA: `d26388e` (계약 커밋, base `6f71814`)
- 학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토·외부 AI 호출·의존성 설치·push: 0회 (계약 금지)
- `development-progress.json`·`PROGRESS_CRITERIA.md`는 allowed_files 밖이라 읽기만 했다. 점수·history 변경 없음.

## 1. 이 세션의 실행 제약 (실측)

이 worktree의 비대화형 세션에서 다음 명령은 모두 "requires approval"로 실행되지 않았다.

| 시도 | 결과 |
|---|---|
| `.venv/bin/python -c 'import card_condition; ...'` | 승인 필요, 미실행 |
| `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage` | 승인 필요, 미실행 |
| `./develop --check` | 승인 필요, 미실행 |
| `ps -o ... -p 3347` (잠금 소유 확인) | 승인 필요, 미실행 |

`artifacts/development-cycle/workspace.lock`에 `{"pid": 3347, "operation": "development edit"}`가 있다(08:00 생성). 이 세션을 감싼 `./develop` 잠금인지 확인하지 못했다.

판단: 단위 테스트를 한 번도 실행할 수 없는 상태에서 `card_condition/` 소스를 바꾸면 검증 없는 변경을 Codex 통합 단계로 넘기게 된다. 그래서 소스·테스트는 바꾸지 않고 읽기 전용 분석만 했다.

## 2. pending 항목별 차단 요인

| 항목 | 배점 | 차단 요인 | 이 worktree에서 가능한가 |
|---|---:|---|---|
| A3 전 범위 평가 자료 | 5 | 셀별 양성/정상 20단위·5실물 부족 (train 10셀 중 2셀 충족, val 0셀). `data_coverage.py`는 이미 감사 기능을 갖췄다. | 아니오. 데이터 확보와 사람 정답이 필요하다. |
| C1~C5 탐지 품질 | 35 | 동일 후보의 앞뒤 5질문 FN≤5%·FP≤10%. 최신 표면 후보도 FN12/94·FP13/53으로 미통과. | 아니오. 학습·비교가 금지다. |
| C1~C3 typed point 조건 | (C 안) | 아래 3.1의 도구 공백이 있다. | 계약·설계까지만 가능하다. |
| D1~D3 독립 검증 | 15 | 미사용 시험셋(질문/면별 각 30실물)이 없다. | 아니오. |
| E2 전 범위 시나리오 | 5 | 비보류 coverage≥70%를 판정할 집계가 없다(3.2). 사용자 시나리오 완주 기록도 없다. | 계약·설계까지만 가능하다. |
| F1·F2 운영 | 10 | 품질 통과 후보·배포 승인·7일 시범이 없다. | 아니오. |

결론: 남은 70점은 모두 데이터·학습·실사용 근거가 있어야 한다. 도구만 추가해서 올릴 수 있는 항목은 없다. 아래 두 공백은 데이터가 확보된 뒤 판정이 막히지 않도록 미리 메울 수 있는 부분이다.

## 3. 코드 근거가 있는 도구 공백

### 3.1 고정 후보 평가에 typed point 응답 입력 경로가 없음

- `card_condition/evaluation_suite.py:69`는 엣지·모서리·표면 셀의 `typed_point_response`를 항상 `status='unmeasured'`로 둔다.
- `numeric_gates.c_raw_all_questions`(`evaluation_suite.py:76`)는 구역 FN/FP만 본다. 이 동작은 의도된 것이다. `tests/test_evaluation_suite.py:91-106`이 "raw gate는 true여도 실제점은 unmeasured"를 고정한다.
- 그런데 C1~C3 완료조건에는 "올바른 종류의 실제점 양성반응 누락≤5%(앞뒤 각 20점·5실물 이상)"가 들어 있다. 현재 표면 후보의 typed 점수는 모델별 token map(`tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py:168-183`, `human_token` 위치 점수)으로 계산한다. 구역 확률로는 이 값을 대신할 수 없다.
- 영향: 데이터가 확보돼도 고정 후보 평가만으로는 C1~C3 21점을 판정할 수 없다. 별도 worker 출력을 사람이 수동으로 대조해야 한다.
- 제안 task(사람 입력 불필요): 역할별 저장 보고서에 `typed_point_predictions`(card_id·side·label·point·score, 모델 SHA·seal 결속)를 선택적으로 받는다. 셀별 `points/missed_points/groups`를 계산하고, 앞뒤 각 20점·5실물 미만이면 `numeric_condition_met=false`로 둔다. 기존 raw gate와 기존 테스트 기대값은 그대로 유지하고, 새 gate `c_typed_point_all`만 추가한다. 실제점 정의(어느 점이 "올바른 종류"인지)는 `point_dataset.point_for_label`와 같은 규칙을 쓴다.

### 3.2 E2 비보류 coverage를 판정할 집계 없음

- E2 완료조건: "사람이 관찰가능하다고 확인한 알려진 필수셀 중 모델 비보류 coverage≥70%". 비슷한 계산은 `score_diagnostics.py:6-29,55-65`(`coverage_known`)와 `observation_clearance.py:34`(`clearance_coverage`)에 있다. 하지만 둘 다 검증 라벨에서 임계 구간별 보류를 탐색하는 연구 진단이다. 고정 릴리스의 실제 hold 정책이나 전 범위 필수셀을 분모로 쓰지 않는다. E2 판정에 바로 쓸 수 있는 집계는 찾지 못했다.
- 주의: 고정 평가 보고의 `probabilities=None`은 미지원 또는 대상 밖 구역이다. 보류가 아니다. 그래서 `question_cells`의 `unavailable_*_scores`로 E2를 계산하면 의미가 섞인다. 보류는 매물 API(`listing_model`)의 hold reason 기준으로 세야 한다.
- 제안 task: `listing_review` 완료 기록에서 사람이 관찰가능으로 확인한 셀을 분모로 둔다. 모델이 보류하지 않은 셀을 분자로 세고, 배경·사진누락·미지원은 정상으로 세지 않는다. 사람 검토 기록이 들어오기 전까지는 판정 불가(`None`)로 둔다.

## 4. 성능 수치

새 평가를 하지 않았다. 아래는 기존 수치를 다시 인용한 것이고, 성능 변화는 측정하지 않았다.

- 표면 최신 후보 `20261024T093945-04a7e5e8`: 개발 147구역 FN 12/94, FP 13/53, typed 실제점 FN 20/51.
- 독립 평가가 없으므로 일반화 개선은 확인되지 않았다.

## 5. 변경·검증·리스크·롤백

- 변경 파일: 이 문서와 `task-1027-2-progress-gap-20261027.html` (모두 `docs/collaboration/reports/`)
- 실행 검증: `git diff --check`만 실행했다. Python 테스트는 실행하지 못했다(1절).
- 리스크: 3.1·3.2는 코드 열람 근거의 제안이다. 실행 재현은 하지 않았다.
- 롤백: 이 커밋을 `git revert <sha>`로 되돌리면 된다. 소스 영향은 없다.

## 6. 사람 확인이 필요한 것

- 다음 세션에서 Claude worktree의 `.venv/bin/python`·`./develop` 실행을 허용해야 3.1·3.2 구현과 단위 검증을 진행할 수 있다(권한 설정 또는 대화형 승인).
