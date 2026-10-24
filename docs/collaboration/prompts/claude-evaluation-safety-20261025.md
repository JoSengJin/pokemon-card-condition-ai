# Claude 평가 입력·출력 안전성 묶음

AGENTS.md, PAIR_CODING.md, docs/collaboration/HTML_REPORTING.md와 docs/collaboration/tasks/evaluation-input-output-safety-batch-20261025.md를 읽고 6단계를 수행하세요.

합성 사진/manifest/metadata와 반드시 patch된 analyzer만 사용해 개발 이력 오염·ID/group/decoded 중복·읽기 단계 사이 입력 변경·저장 실패/경쟁 출력을 검사하세요. 실제 결함만 실패 검사부터 남기고 허용11파일 안에서 최소 수정하세요. source 편집은 ./develop 잠금 안에서 합니다. 단계별 커밋 후 다음 독립 작업을 계속하세요.

자체 venv는 이미 이 worktree에 있습니다. 새 브랜치와 import 경로를 확인하고 과거 ignored artifacts/실제 사진·모델은 읽지 마세요. 실제 학습/추론이 들어 있는 test_side_evaluation/test_region_evaluation/test_point_final_evaluation/test_pipeline 전체를 실행하지 마세요. 계약에 지정한 mock 검사만 실행하세요.

파일당 함수7개/호출 전이4회 제한과 근거 기록을 지키세요. 성과·진척 HTML을 실제 생성·검증·열기까지 수행하고 열기 요청/렌더 확인 결과를 구분하세요. 실제 모델 품질 개선이나 전체 진척 상승으로 포장하지 마세요.

최종 전체 SHA 순서·변경 파일·실제 검사·HTML 경로/열기 결과·미검증·리스크·롤백을 한 번에 인계하세요. Mastra·실제 AI 호출·main 통합·push는 하지 마세요. 검증/통합/원격 push는 Codex가 담당합니다.
