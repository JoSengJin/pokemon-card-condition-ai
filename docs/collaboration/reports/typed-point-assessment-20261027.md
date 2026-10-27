# 실제점 응답 집계 — 2026-10-27

개발 진척률 **30/100 (usable-card-analysis-v1.0, +0%p)**. 이번 성과: 봉인된 사람 결함점의 저장 점수를 C1~C3 여섯 셀로 집계하는 선택 경로 구현 및 통합 회귀75개 통과. 실제 모델 성능 개선은 미평가.

## 변경 파일과 핵심 diff

- `card_condition/evaluation_typed_points.py`: 사람 defect_points의 종류·좌표 객체·카드·면을 저장 보고서와 정확히 대조. 같은 decoded 사진의 동일 점 중복·누락·추가·비유한/범위 밖/미지원 점수를 거절한다. 면의 같은 종류 양성 라벨이 확인된 기존 점만 대상으로 삼는다. 제외 자료는 제외하고, 확인 안 된 정상/결함을 생성하지 않는다.
- `card_condition/evaluation_suite.py`: region_final의 선택적 typed_point_predictions를 처리. 기존 raw gate를 보존하고 `c_typed_point_all`을 추가. 점수 없음은 unmeasured, null은 unavailable, 분모/실물 수 부족은 false. 임계값 .5, 앞뒤·종류별 20점/5실물 이상 및 누락률<=5%만 수치조건 통과. 독립성/운영 준비 flag는 계속 false.
- `tests/test_evaluation_typed_points.py`: 임계경계, 20점/5실물 부족, 점수 누락·오류, 종류/좌표/ID/면 불일치, 사진 별칭, SHA 불일치와 통합 출력 보존을 합성 검사.
- `tests/test_evaluation_suite.py`: 기존 raw gate 기대값은 유지하고 실제점 미측정 gate를 명시. 사람점이 있는 합성 fixture 선택 지원.
- task 계약 및 이 MD/HTML 보고서.

## 입력 계약

기존 role 보고서에 `typed_point_predictions: [{card_id, side, label, point, score}]`를 선택적으로 포함한다. point는 봉인 manifest의 defect_points 객체 전체와 일치해야 한다(선택 types도 보존). score는 원래 사진 좌표의 해당 종류 응답이며, 구역 최대 점수로 대체할 수 없다. 모든 적격 기존 점이 정확히 한 번씩 있어야 하며, 미지원은 score=null로 기록해 분모를 보존한다. 필드 자체가 없으면 기존 보고서를 받아 미측정으로 둔다.

모델 SHA·candidate/seal/manifest·원래 report SHA·노출 receipt·입력 해시는 기존 matched_reports 검증을 상속한다. 보고서 해시 결속은 실제 token-map 추출의 올바름/독립성을 증명하지 않는다. 생산 worker에서의 실제점 점수 내보내기는 이번 범위에 없으며, 기존 보고서를 소급 수정하거나 새 추론하지 않았다.

## 실제 검증

- 검증 소스 SHA: cae59f1408d214edd514d279864d715c9199e2df
- 격리 worktree: 15모듈 합성 회귀75개, 4.049초, OK.
- main 통합 후 동일15모듈 회귀75개, 4.337초, OK. 정본 로그: `artifacts/typed-point-assessment-20261027/tests.log` (Git 제외).
- 명령: `PYTHONPATH=tests .venv/bin/python -m unittest test_evaluation_typed_points test_evaluation_suite test_evaluation_suite_safety test_evaluation_suite_inputs test_frozen_report_loaded_bytes test_frozen_judgment_identity test_question_area_scope test_unsupported_truth_identity test_physical_uncertainty test_physical_uncertainty_evaluation test_point_dataset test_frozen_candidate test_frozen_test test_frozen_candidate_evaluation test_frozen_test_evaluation`
- `git diff --check` 통과. AST 함수 수: helper2, suite1, 신규검사6, 기존검사7. 변경 소스 최대 호출 전이4.
- 학습·실제 사진 추론·모델 성능 비교·외부 AI 호출·라벨 수정·데이터 수집: 0회. 테스트의 합성 사진/가짜 analyzer는 테스트 임시 폴더에서만 사용.
- 보고서 HTML 열기: 아래 최종 상태 참고. 실제 렌더 확인 전에는 확인했다고 기록하지 않는다.

## 성능·남은 의존

새 평가가 없으므로 FN/FP/%p 변화는 미측정이며, 독립 일반화·운영 개선은 미확인. 기존 기준선 재인용: 표면 개발147구역 FN12/94·FP13/53, typed FN20/51 (PROGRESS_CRITERIA.md). 이번 합성 .5 점수는 성능 결과가 아니다.

클로드의 데이터 보완 checkout·라벨·사진·모델·coverage 구현·consumer는 수정하지 않았다. 독립 작업만 별도 worktree에서 진행했다. 현재 A3/D1과 C/E/F의 실제 완료 증거는 여전히 부족하다.

다음 실제 검증은 봉인된 자료와 같은 후보의 모델별 실제점 점수 산출 근거가 필요하다. E2 coverage는 review의 ground_truth=false 기록을 알려진 평가 정답으로 승격해서 계산할 수 없다. 지역별 관찰가능·정답 분모와 고정 정책에 결속된 입력 계약이 확보되기 전에는 점수/통과를 만들지 않는다. Claude 소유의 모델별 worker나 평가자료를 변경해 이 의존을 우회하지 않는다.

## 리스크와 롤백

외부 호출자가 numeric_gates.values() 전체를 통과 조건으로 쓰면 새 실제점 gate 때문에 미측정 자료가 더 보수적으로 실패한다. 저장 보고서 스키마는 선택 필드만 확장했고 raw gate 값은 그대로다. 저장 점수의 추출 출처는 별도 검증이 필요하다.

코드 롤백: `./develop -- git revert cae59f1408d214edd514d279864d715c9199e2df` 후 위 회귀와 일반 push. 데이터/모델 snapshot 복구 불필요. 계약 커밋은 8f0a573. 원격 동기화와 worktree 정리의 확인 시점은 최종 인계에 기록한다.

## 에튜 포인트

고정 분모: 응답 없는 점을 빼면 누락률이 좋아 보인다. 이 코드는 null 점수를 unavailable로 남겨 통과를 막는다. 예를 들어20점 중19개만 응답하면19/19 성공으로 승인하지 않는다.

## 원격·열기·worktree 최종 확인

- 코드 main/origin SHA `cae59f1408d214edd514d279864d715c9199e2df` 일치 확인 후 문서 인계를 별도 커밋한다.
- HTML: Codex 브라우저 열기도구 `queued` 반환. 열기 요청 전달, 실제 렌더 미확인. 문서와 HTML 본문 일치·외부 script/API 없음은 정적 검사했다.
- 이전 Codex `codex/frozen-report-loaded-bytes-20261026`의 고유4커밋 모두 main cherry-pick 대응 확인, clean·개발 잠금 비차단 획득·Git 작업 없음·고유 lock 증거 SHA 보존 후 일반 worktree remove 성공. 브랜치/이력은 보존.
- 최근 완료 `codex/typed-point-assessment-20261027` checkout 유지. 다른 Codex 및 Claude 데이터/미통합 checkout은 정리 대상에서 제외하고 보존했다. 감사: `artifacts/typed-point-assessment-20261027/worktree-cleanup/audit.json`.
