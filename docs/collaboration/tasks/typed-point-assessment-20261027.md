task_id: typed-point-assessment-20261027
owner: Codex
status: implementing
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
