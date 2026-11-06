# pair-control 관제 화면 턴 이력 보존

- task_id: pair-control-ui-history-20261106
- owner: Codex
- status: integrated
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

## 인계
- 적용 순서 7c96c120e1cc97de08213cdae41f794d80327753 → 계약 3822ed01319aa0448dadeb93829a9f333b77f4d4 → 코드 dad7ead590e5f58f8095dd37f3fb2ee1a054fc53 → 후속 문서. 소스1줄 수정·회귀3개 추가, seed/기존 자동 UI 테스트 변경 없음.
- 수정 전3개 중2통과/1실패로 중복 재현. 수정 후 관련20개 중19통과/실패0/기존 Playwright 건너뜀1. main 동일20개 중19통과/실패0/건너뜀1. 두 위치 typecheck·structure --check 통과, 전체trace 동일. 전체 회귀 재실행 없음.
- view-pipeline 정의5→6, 전체270파일/781정의/최대7/최대전이4/초과0/순환0. renderPipeline 최대2전 유지. 미확인86개/근거 해시 불변·native 분류 미완료0. 외부2735 유지(filter/slice 교체), 승인식/실행 로직 변경 없음.
- 실제 브라우저 기본/현재가 마지막 아닌 상태/빈 상태3종 확인. 수정 전 현재2회·최신 실패0회 → 수정 후 각각1회. 보류·결과 불명·push 완료/미완료 표시 유지. 제품 자동 UI1건 건너뜀과 별개 수동 화면 근거다.
- .claude 해시 c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da 전후 불변. 운영 설정/장부/기존 서버 미변경·모델 호출0·학습/추론0. 새 정리 대상0·checkout8개 보존. 전체 장부78/100 유지.
- HTML docs/collaboration/reports/pair-control-ui-history-20261106.html, 근거 artifacts/pair-control-ui-history-20261106/. 보고서 IAB 열기·첫 화면 실제 렌더 확인 완료, 스크린샷 보존. 롤백은 후속 문서→코드 역순 git revert·관련 검증·일반 push. 실제 롤백 없음.
