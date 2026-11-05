# 질문별 구역·모델 지원 분모 보완

개발 진척률 30/100(usable-card-analysis-v1.0), 이번 점수 +0. 고정 source 정의와 모델 지원 범위를 분리했다. 성능 개선은 평가하지 않았다.

검증 코드: main c103450, 원본 계약 8764fdd / 구현 63f99c4.

## 변경 파일과 diff
- card_condition/physical_uncertainty.py: optional question_areas; canonical 비해당 미확인만 out_of_scope_unknown_units로 별도 공개. 해당 미확인/불명확 구역/known truth는 보존하며 generic 기본 동작 유지.
- card_condition/region_evaluation.py, evaluation_suite.py: 기존 regions.REGION_TARGET_AREAS를 region 역할에만 전달.
- card_condition/evaluation_suite_metrics.py: 모델 미지원이어도 source known 양성/정상·실물·subgroup 수량 유지. 미지원 score는 전부 unavailable, FN/FP=None, C=false. D1 수량과 모델 지원 독립.
- tests/test_evaluation_suite.py: 표면 중앙 구역과 부분 모델 지원 합성 fixture 옵션.
- tests/test_question_area_scope.py: 해당/비해당/불명확/known 미지원/부분 모델의 동결 suite 회귀 6개.
- 이 보고서와 tasks/question-area-scope-20261026.md.

## 실행 검증
- 수정 전 정상 모서리+비해당 중앙 None 조합: corner 정상 실물 0, unknown 1 재현.
- 수정 후 합성 30양성/30정상 실물: 비해당 unknown 60 별도 공개, 정상 분모30, 해당 unknown0. 해당 미확인은 계속 정상 판정을 막음.
- 모델 미지원 대조: source 양성30/정상30 보존, 각각 unavailable30, FN/FP=None, C=false. D1 수량만 source대로 집계하며 verified는 false.
- base PYTHONPATH=tests .venv/bin/python unittest runner: 기존102 + 신규6 = 108 PASS (8.367s). torch threads1. 목록은 test_question_area_scope와 이전 observation-evaluation-model-sha 보고서의 동일102 회귀.
- 수정 소스4/검사2 compileall PASS, AST 함수 3/3/1/1/7/7 <=7, git diff --check PASS. 변경 경로 최대3전이, 새 wrapper 없음.
- 실사진 추론·새 학습·외부 AI 없음. 기존 회귀의 합성 랜덤 모델 forward/mock metadata 평가만 실행. 실제 FN/FP·일반화·Gemini 절감 미측정.

## 리스크와 미완료
- 새 region 진단은 비해당 unknown을 분리하므로 과거 generic 진단과 분모를 그대로 성능 개선으로 비교하면 안 됨. 과거 보고서는 변경하지 않았다.
- known truth는 비해당 위치라도 숨기지 않으며 실제 manifest loader의 geometry/label 검증을 유지한다. 새 통계 필드는 additive.
- D1/D2/D3 인증·실제점 품질·독립 provenance는 여전히 미충족. 데이터 취득과 사람 정답을 기다려야 한다.
- HTML artifacts/question-area-scope-20261026/index.html 생성, 열기 요청 결과는 아래 기록. 실제 렌더 검증과 구분한다.

## 롤백
main 구현 c103450을 git revert c103450으로 되돌리고 관련 회귀 재실행 후 일반 push. 원본 데이터/기존 실험은 수정하지 않았다. 원격 반영 SHA는 세션 Git 로그로 확인한다.

HTML 열기 도구 결과: queued. 열기 요청 전달, 실제 렌더 미확인.
