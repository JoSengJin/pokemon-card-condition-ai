# pair-control 승인 취소·작업 보관 — Claude 배정

- task_id: `pair-control-unapprove-archive-20261026`
- owner: Claude
- status: implementing
- base_sha: `0d01a1b` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 목표

1. **승인 취소**: 승인됨(`approved`·`integration_blocked`) 작업을 같은 SHA로 검토 단계(`review_pending`)로 되돌린다. 에이전트는 다시 실행하지 않는다. 기존 workflow 실행은 `integrate-gate`에서 `withdraw`로 끝내고, 기존 재검토 경로(`reviewOnly` 실행)로 새 실행을 만든다. 같은 SHA·계약의 작업 테스트 결과는 그대로 유효하다.
2. **작업 보관**: 진행 중이거나 결정이 남은(`OCCUPYING`) 작업이 아니면 목록에서 숨긴다. 기록·이벤트·worktree·브랜치는 지우지 않으며 언제든 보관 해제할 수 있다.

## allowed_files

1. `tools/pair-control/src/executor/taskControl.ts` (신규)
2. `tools/pair-control/src/executor/executor.ts` (Task에 `archivedAt` 필드 1줄만)
3. `tools/pair-control/src/workflow.ts` (`integrate-gate` resume에 `withdraw` 분기)
4. `tools/pair-control/src/mastra/index.ts` (경로 2개)
5. `tools/pair-control/src/ui/**`
6. `tools/pair-control/test/task-control.test.ts` (신규), `test/ui-stages.test.ts`
7. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-unapprove-archive-20261026.html`

## forbidden

위 목록 밖. 다른 실행기 동작·승인 검증 규칙은 바꾸지 않는다. 사용자의 4111 서버를 종료·재시작하지 않고, 실제 작업(task-1026-1)에 승인 취소·보관을 실행하지 않는다.

## 구조 기준

- 새 파일 `taskControl.ts`는 함수 7개 이하. `executor.ts`·`runtime.ts`의 기존 함수 수 초과는 범위 밖 부채이며, 이번에 함수를 더하지 않는다(필드 1줄만).
- 승인 취소 경로: `route → withdrawApproval → resume(old run) | startReview(기존)` 전이 2~3회.

## checks

1. `npm run typecheck`, `npm test`(기존 67 + 신규).
2. 신규 검사: 승인 취소 후 `review_pending`·같은 SHA·승인 기록 없음·에이전트 실행 수 그대로·작업 테스트 유효·다시 승인→통합 가능; 승인 전 상태에서 거부; 보관은 진행 중 작업 거부, 끝난 작업 보관·해제 시 기록 유지.
3. 브라우저(4111, 읽기 전용): 버튼 표시·보관 목록 렌더. 실제 작업에는 실행하지 않는다.
4. 성과·진척 HTML 생성·열기, `git diff --check`, 최종 깨끗한 트리.

## 결과

(인계 시 갱신)
