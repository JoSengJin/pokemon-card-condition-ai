# pair-control 관제 화면 턴 이력 보존

- task_id: pair-control-ui-history-20261106
- owner: Codex
- status: implementing
- base_sha: 7c96c120e1cc97de08213cdae41f794d80327753
- branch: codex/pair-control-ui-history-20261106
- goal: 서버가 현재 턴으로 선택한 항목이 배열 마지막이 아니어도 현재·나머지 턴을 누락/중복 없이 표시하고 실제 관제 화면으로 확인한다.
- allowed_files: tools/pair-control/src/ui/js/view-pipeline.js, tools/pair-control/test/ui-pipeline-render.test.ts, tools/pair-control/test/ui-seed.ts, tools/pair-control/test/ui-pipeline.test.ts, 이 계약, docs/collaboration/reports/pair-control-ui-history-20261106.html.
- forbidden_files: 운영 설정/상태/장부·.claude/·모델/worker·사진/라벨·진척 기준·다른 worktree/서버. 실제 모델 요청/학습/추론 금지.
- contract: pipelineView가 선택한 currentTurn.id로 현재 턴을 구별하고 나머지 이력을 보존. 기존 승인식/실행 로직 변경 없음. UI 합성 상태는 기존 seed/setup을 재사용하고 검증 서버는 GET만 허용해 모델 실행 경로 없음.
- structure: 시작270파일/780정의, view-pipeline.js5정의. 파일당 최대7·실제 전이4 유지. 경계·콜백으로 깊이 숨기기 금지.
- checks: 수정 전 누락/중복 재현 → 최소 수정 → UI 관련 회귀·typecheck·structure --check → 실제 브라우저 관제 화면(기본/현재 턴이 마지막 아닌 상태/빈 상태) 및 HTML 렌더. main 관련 회귀/구조·.claude 해시 보존·잠금/프로세스 확인 후 일반 push·원격 SHA 대조. 전체 회귀는 실행 범위와 구분하여 기록한다.
- experiment: 없음. 카드 모델 성능·전체 진척 변경 없음.
- rollback: 후속 커밋 역순 git revert, 검증 후 일반 push. 운영 장부·결과 불명 실행 재수행 금지.

## 읽기 근거
- pipelineView.ts는 turns 중 진행 중인 턴을 currentTurn으로 선택하며 마지막 요소라고 보장하지 않는다. view-pipeline.js는 turns.slice(0,-1)로 이력을 만들고 있어 선택된 현재 턴이 마지막이 아니면 중복과 최신 턴 누락이 생긴다. 배열 위치 대신 ID로 구별해야 한다.
- 기존 자동 UI 검사는 Playwright 미설치로 건너뜀1이며, 실제 화면 확인은 CUA로 수행해 자동 테스트 결과와 구분한다.
