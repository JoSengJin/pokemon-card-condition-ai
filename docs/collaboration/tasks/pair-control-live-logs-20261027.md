# pair-control 단계별 실시간 로그 — Claude 배정

- task_id: `pair-control-live-logs-20261027`
- owner: Claude
- status: implementing
- base_sha: `2940df4` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 배경

ArgoCD에서 파드를 눌러 로그를 보듯, 단계 노드를 누르면 그 단계의 출력이 실시간으로 보이게 한다(사용자 승인된 화면 예시 기준). 지금은 에이전트·작업 테스트·리뷰 로그를 1초마다 이어받지만 접힌 칸에 숨어 있고 한 번에 하나만 볼 수 있으며, 통합 후 검사는 끝난 뒤 한꺼번에 파일에 쓰여 화면에서 볼 수 없고, 수동 모드는 볼 출력이 없다.

## 목표

1. **단계 패널 안의 로그 창**: 구현(에이전트)·작업 테스트(명령별 선택)·리뷰·통합 후 검사 패널에 로그 창을 둔다. 상태(실행 중 ●·PID·경과 / 종료·종료코드), 따라가기 켜짐/꺼짐, 일시정지, 복사, 찾기(일치 줄만 표시), 줄 수.
2. **통합 후 검사 실시간화**: 출력을 줄 단위로 가린 뒤(비밀 패턴) 로그 파일에 즉시 쓰고, 실행 중에도 화면이 이어받게 한다. 통합 기록에 실행 중 항목을 먼저 남긴다. 서버가 작업 상태의 항목에서만 파일을 찾는다(클라이언트가 경로를 주지 않음).
3. **수동 모드 활동 표시**: 작업 폴더의 새 커밋·변경 파일·범위 밖 변경 개수를 보여 준다(출력이 없는 대신).

## allowed_files

1. `tools/pair-control/src/executor/logstream.ts` (신규: 줄 단위 가림 + 즉시 기록 실행, 파일 이어받기)
2. `tools/pair-control/src/executor/taskControl.ts` (활동 조회, 통합 후 로그 조회)
3. `tools/pair-control/src/executor/executor.ts` (`runPostChecks` 본문과 `integration.postStatus`에 `running` 추가만)
4. `tools/pair-control/src/mastra/index.ts` (경로 2개)
5. `tools/pair-control/src/ui/**` (신규 `js/logview.js`)
6. `tools/pair-control/test/logs.test.ts` (신규), `test/ui-stages.test.ts`
7. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-live-logs-20261027.html`

## forbidden

위 밖 전부. 로그 내용·비밀 가림 규칙(`SECRET_PATTERNS`), 통합·검사의 판정 규칙, 무과금 가드는 바꾸지 않는다. 사용자의 실제 서버·작업에서 새 흐름을 실행하지 않는다(합성 데모와 mock 프로세스만).

## 구조 기준

`logstream.ts` 7개 이하, `logview.js` 7개 이하, `taskControl.ts` 7개 이하, 호출 전이 4회 이하(`route → tailPostLog → tailFile`, `refresh/pollLog → logTarget`). `executor.ts`는 기존 파일(변경은 한 함수 본문과 타입 한 토큰).

## checks

1. `npm run typecheck`, `npm test`(기존 77 + 신규).
2. 신규: 줄 단위 가림(비밀이 청크 경계에 걸려도 가려짐)·즉시 기록·타임아웃 종료; 통합 후 검사 실행 중에 로그가 늘고 끝나면 완성·항목 상태 반영; 활동 조회(커밋·변경·범위 밖); 단계 판정(통합 중 통합 후 검사 진행 중).
3. 합성 데모 서버에서 mock 작업(느린 성공)으로 구현 단계 로그가 실시간으로 늘어나는지, 일시정지·따라가기·찾기·복사 동작 확인(실제 모델 호출 없음).
4. 성과·진척 HTML 생성·열기, `git diff --check`, 최종 깨끗한 트리. 확인 후 데모 서버 종료.

## 결과

(인계 시 갱신)
