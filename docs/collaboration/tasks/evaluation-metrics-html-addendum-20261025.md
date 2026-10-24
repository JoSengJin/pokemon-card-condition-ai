# 평가 수치 작업 HTML 인계 보완

사용자 요청: 다음 개발 보고부터 Claude도 성과·진척 HTML을 실제로 연다.

대상: evaluation-metrics-contract-batch-20261025. 기존 task의 합성 평가/모델 실행 금지는 유지한다. 작업 중인 Claude 소유 task를 Codex가 병행 수정하지 않고 이 보완 계약으로 범위를 추가한다.

- 추가 허용 파일: docs/collaboration/reports/evaluation-metrics-contract-batch-20261025.html (신규). 기존 allowed_files 9개에 이 파일을 더한 10개만 허용한다.
- 기존 task의 HTML/UI 생성 금지는 제품 기능/별도 도구를 뜻하며, 사용자 요청에 따른 이 정적 성과 보고 HTML은 예외로 허용한다.
- docs/collaboration/HTML_REPORTING.md를 적용한다. 현재 worktree에 없으면 사용자가 전달한 기본 checkout의 문서를 읽기 전용으로 읽는다. 기본 checkout을 수정하거나 실행 중 코드를 덮어쓰지 않는다.
- 합성 테스트의 손계산 기대/실행 결과·반례·보정·실제 테스트 수·변경 파일·구조 기준·미검증·리스크·롤백을 표시한다. 진척은 고정 기준 30/100이며 보고 시 정본을 대조한다. 실제 모델 성능 비교는 없음을 표시한다.
- HTML 내용과 실제 로그/Markdown 보고서를 대조한다. 독립 HTML의 외부 요청/비밀값/개인 경로 포함 여부를 검사한다. 문서 커밋 SHA와 테스트한 코드 SHA를 구분한다.
- 최종 인계 전에 HTML을 실제로 여는 동작을 수행하고 열기 요청 성공/렌더 확인/차단을 정확히 보고한다. 열기가 차단되면 오류와 절대경로 링크를 남긴다. 열기 명령만 성공했는데 화면을 확인했다고 말하지 않는다.
- Claude가 자기 task 문서의 allowed_files/checks/handoff에 이 추가 조건을 기록한다. 현재 브랜치를 main으로 덮어쓰거나 rebase하지 않는다. 기존 작업에 이어 별도 문서/HTML 커밋으로 인계할 수 있다.
