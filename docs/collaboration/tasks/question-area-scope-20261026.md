task_id: question-area-scope-20261026
owner: Codex
status: implementing
base_sha: 79b4d064b378c27e3f1066cb0075f737539692d2
branch: codex/question-area-scope-20261026
goal: 고정 구역 정의에서 비해당 미확인과 해당 미확인을 구분하고, 모델 지원 여부와 source 정답 수량을 분리한다.
allowed_files:
- card_condition/physical_uncertainty.py
- card_condition/region_evaluation.py
- card_condition/evaluation_suite.py
- card_condition/evaluation_suite_metrics.py
- tests/test_evaluation_suite.py
- tests/test_question_area_scope.py
- docs/collaboration/tasks/question-area-scope-20261026.md
- docs/collaboration/reports/question-area-scope-20261026.md
- ignored artifacts/question-area-scope-20261026/index.html
forbidden_files: 다른 소스/실자료/정답/기존 실험/진척 수치/Claude 소유 파일
contract:
- regions.REGION_TARGET_AREAS 정본만 사용한다. optional question_areas가 있을 때 canonical 구역의 비해당 truth=None만 제외하고 out_of_scope_unknown_units로 공개한다. 해당 미확인, 불명확 구역, known truth는 보존한다. mapping 없는 generic 호출은 기존 보수적 집계를 유지한다.
- source known 양성/정상 수량과 subgroup은 모델 미지원에도 보존한다. 미지원 score는 모두 unavailable, rate=None, C 통과 금지. D1 수량은 실제 source만 집계한다. 미기록 역할의 source는 추정하지 않는다.
- threshold/정답/고정 배점/verified=false/모델 추론을 변경하지 않는다. region 평가와 suite에만 scope를 전달한다.
structure: physical_uncertainty 3→3, region_evaluation 1→1, suite 1→1, metrics 3→3, existing fixture 7→7, new tests <=7. assess→question_cells→subgroup_denominators 및 assess→physical_uncertainty→event_summary→wilson_upper 최대 3전이. 새 wrapper 없음.
checks: 수정 전 center 비해당 unknown 때문에 corner 정상 실물 0/unknown 1 재현. 수정 후 해당/비해당/불명확/known missing/미지원 수량/동결 suite 합성 대조, 기존102회귀, AST/compile/diff. 실사진 추론·학습·외부 AI 없음. HTML 생성·열기/렌더 구분, main 통합 및 push.
experiment: 없음. 합성 통계/저장 보고서 재집계이며 모델 성능 실험 아님.
handoff: 변경 파일/실제 검사/리스크/롤백/원격 상태/HTML 기록. progress 30/100 유지.
