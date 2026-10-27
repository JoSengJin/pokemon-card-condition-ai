task_id: typed-point-assessment-20261027
owner: Codex
status: integrated
base_sha: c6babdf60192e99946af56ae5011b447b23c721e
branch: codex/typed-point-assessment-20261027

goal: 고정 후보의 저장 보고서에 선택적으로 포함된 실제점 응답을 봉인한 사람 좌표와 대조하고 C1~C3의 여섯 셀 수치조건을 별도 집계한다.

allowed_files:
- card_condition/evaluation_typed_points.py
- card_condition/evaluation_suite.py
- tests/test_evaluation_typed_points.py
- tests/test_evaluation_suite.py
- docs/collaboration/tasks/typed-point-assessment-20261027.md
- docs/collaboration/reports/typed-point-assessment-20261027.html
- docs/collaboration/reports/typed-point-assessment-20261027.md

forbidden_files: 데이터 확보·coverage·라벨·사진·모델·기존 실험·점수/기준·Claude checkout·consumer·비밀 설정. 실제 학습/사진 추론/AI 호출 없음.

contract: 기존 raw gate는 보존. region_final 보고서의 typed_point_predictions는 선택적이며 없으면 unmeasured. 항목은 card_id/side/label/point/score이며 봉인 manifest의 같은 종류 양성 defect_points를 정확히 한 번씩 포함한다. point는 원본 객체 전체와 같아야 한다. 점수는 유한한 [0,1] 또는 null(미지원). 모델/후보/seal/manifest/report SHA는 기존 matched_reports 검증을 상속한다. 점이 없거나 20점/5실물 미만·누락점수면 통과 불가. .5 고정, FN<=5%. 구역 점수·정상 라벨 생성 금지. 중복 decoded 사진의 동일 점은 거절. 기존 입력/출력 보존.

structure: 신규 helper 2함수 이내, evaluation_suite 1→1; assess_suite→typed_point_cells→checked_typed_points 2전이. 입력 검증 경로의 기존 깊이는 유지. 테스트 파일 7함수 이하.
checks: 신규 합성 단위검사; canonical 통합 후 evaluation_suite 및 인접 frozen/identity 회귀; git diff --check. 실제 모델/성능 검증 없음.
experiment: 불필요(저장 점수 집계만).
HTML: docs/collaboration/reports/typed-point-assessment-20261027.html. 실제 검사 결과·30/100·위험·롤백을 표시하고 로컬 열기 요청/렌더 결과를 구분.
handoff: 완료 시 아래 추가. 미통합 Claude 작업·사용 중 checkout은 보존한다.

## 구현 인계

- status: ready_for_review
- 코드: 새 helper 2함수, suite 1함수; 테스트 6/7함수(AST 실측). assess_suite→typed_point_cells→checked_typed_points→validate_annotations→validate_defect_points/validate_visibility_points 최대4전이. 표준 라이브러리 내부와 기존 별도 모델 실행 경로는 새 호출에 포함하지 않는다.
- 격리 환경에서 card_condition import가 현재 checkout을 가리키는 것을 확인했다. 의존성은 기존 설치본을 새 venv에 독립 복사했으며 공유 symlink·새 다운로드·editable 설치는 없다.
- 합성 회귀75개 통과(15개 모듈), git diff --check 통과. 실제 학습·사진 추론·성능평가·외부 AI 호출 0회.
- typed_point_predictions는 원래 보고서 SHA로 보호되는 선택 입력이다. 생산 worker의 실제 token-map 점수 내보내기는 이번에 실행하거나 추가하지 않았다. 수치집계는 점수의 산출 과정/독립성을 증명하지 않는다.
- 진척30/100 유지. E2 비보류 coverage는 별도 의존으로 남는다. 기존 review 기록은 ground_truth=false이고 지역별 관찰가능한 알려진 평가 정답을 제공하지 않으므로 임의로 평가 분모로 사용하지 않는다.
- 위험: numeric_gates에 c_typed_point_all=false가 추가된다. 모든 gate를 함께 요구하는 호출자는 점수 미제공 시 더 보수적으로 실패한다. 기존 raw gate 값은 보존.
- 롤백: 통합 커밋을 ./develop -- git revert로 되돌리고 관련 검사 후 일반 push. 원본 데이터/모델 복구 불필요.
- main 통합 후 동일75개 재검사와 HTML 열기 결과를 별도 보고서에 기록한다.


## Codex 통합 완료

- source: 7952ef4 → main cae59f1408d214edd514d279864d715c9199e2df. 계약은8f0a573.
- main 회귀75개 OK, diff 검사·허용7파일 대조·AST2/1/6/7함수 확인. 실제 성능 평가는 없음.
- 코드 main/origin SHA 일치 확인. 보고 MD/HTML은 후속 문서 커밋으로 push한다.
- HTML 열기도구 queued(요청 전달), 실제 렌더 미확인. MD와 HTML 본문 정적 일치 확인.
- 이전 Codex frozen-report-loaded-bytes 작업 checkout은 고유4커밋 통합·clean·잠금·증거보존 확인 후 일반 제거. branch/SHA 보존. 현재 typed-point-assessment checkout은 최근 완료 롤백용 유지. Claude와 기타 작업 checkout은 그대로 보존.
