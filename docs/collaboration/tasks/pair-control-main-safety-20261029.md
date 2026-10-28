# 작업 계약: pair-control 메인 교대 안전성·검증 결함 수정

- task_id: `pair-control-main-safety-20261029`
- owner: Claude (구현)
- status: implementing
- base_sha: `0f8849271685437365796edee38b7fbd4e3586fd`
- branch: `claude/pair-control` (기존 worktree, 미커밋 변경 없음 확인)
- 통합·push·실제 모델 호출: 하지 않음(현재 메인이 검토 후 처리)
- 근거: `artifacts/pair-control-main-rotation-review-20261029/REPORT.md`(기본 checkout, 읽기 전용), 그 폴더의 repro.log·concurrency.log·review-*.mts는 검토용 fixture이며 제품 코드로 복사하지 않고 회귀 테스트로 옮긴다.
- 분리 작업: "교대 후 연속 작업 연결"(검토 P1-6)은 이 작업에 포함하지 않는다. 이 작업만으로 연속 페어코딩 완성이라고 보고하지 않는다.

## 목표

검토에서 재현된 P1 5건과 P2 1건을 반례 회귀 테스트로 먼저 고정하고, 기존 main-role-rotation 계약(완료 조건 7개)을 깨지 않고 수정한다.

## 완료 조건

1. 승인 대상=실제 배정 대상: assign_task는 실제 task ID와 입력을 먼저 확정하고 같은 ID로 승인 검사·실행한다. 바깥 taskId와 input.taskId가 다르면 거부한다.
2. 조건부 승인: 기계 검증 가능한 조건 `requires.handoffConfirmed`(메인 확인된 인계 + 승인 SHA가 결과 HEAD와 일치)만 구조화한다. 자유 문장 `conditions`만 있고 구조화 조건이 없는 승인(기존 장부 포함)은 자동 수행을 보류하며 무조건 승인으로 바꾸지 않는다.
3. 통합 결과: 행동 성공은 작업이 실제로 `integrated`이고 통합 HEAD가 있으며 필수 통합 후 검사가 통과(검사가 없으면 not_run 허용)일 때만 기록한다. 승인 행동도 실제 `approved` 상태를 확인한다. blocked/refused/conflict/check_failed는 ok:false이며 교대 completed 근거가 아니다.
4. 잘못된 응답: 인수 전에 응답 전체·행동 목록·각 항목을 검증한다. 실패하면 메인·세대를 바꾸지 않고 체크포인트와 실패 근거를 남기며 감시 루프로 예외를 내보내지 않는다.
5. 소유권·중복: 각 행동 직전 세션·세대·정지 상태를 확인하고, 행동 실행과 교대를 직렬화하며, 행동 ID를 실행 전에 영속 표시해 검사·실행·기록 사이 중복을 막는다. 결과 불명(수행 중 표시만 남은) 행동은 재실행하지 않는다.
6. 구조 기준: onMainEnd→ackSession→applyActions→runOne→mainOps→실행기 경로와 stable 재귀를 `scripts/structure-trace.mjs`로 파일 경계를 넘어 측정해 보고한다. 기준 충족이 불가능한 부분은 실제 경로와 필요한 예외를 보고하고 그 부분의 채택을 보류한다(임의 예외·통과 표시 금지).

## 허용 파일

- 수정: `tools/pair-control/src/executor/mainActions.ts`, `mainApprovals.ts`, `mainHandover.ts`, `mainTypes.ts`, `mainCheckpoint.ts`(stable 재귀 제거만), `executor.ts`(onMainEnd import 경로만), `prepare.ts`(suggestTaskId export만), `tools/pair-control/src/runtime.ts`(화면 요약에 requires 표시만), `tools/pair-control/src/mastra/index.ts`(승인 API가 `requires`를 전달만), `tools/pair-control/test/main-rotation.test.ts`(기존 기대 갱신이 필요할 때만)
- 신규: `tools/pair-control/src/executor/mainEnd.ts`(onMainEnd 이동·예외 차단), `mainGuard.ts`(응답 검증), `mainSerial.ts`(직렬화), `mainOutcome.ts`(실제 결과 확인), `tools/pair-control/test/main-safety.test.ts`, `tools/pair-control/scripts/structure-trace.mjs`
- 문서: 이 계약, `docs/collaboration/reports/main-safety-20261029.html`, `tools/pair-control/README.md`(조건 의미 한 단락)
- 금지: `AGENTS.md`/`PAIR_CODING.md`(이 브랜치 사본은 main보다 오래됨 — 통째 복사·수정 금지), 데이터·라벨·모델·운영 코드, 기본 checkout, 운영 `.state`·승인 장부, 실제 Codex/Claude/Gemini 호출.

## 검사

- `npm run typecheck`, 관련 회귀(`test/main-safety.test.ts`, `test/main-rotation.test.ts`), `npm test` 전체. 모두 fake CLI/mock이며 실제 CLI 검증이 아니다.
- 반례: 승인 밖 배정, 조건 미충족·검증 불가 조건, 통합 차단/거절/충돌/검사 실패, actions:{}·잘못된 항목, 실행 중 세대 변경, 동일 ID 동시/중복.
- 구조: `node scripts/structure-trace.mjs <시작함수> <파일...>` 결과(함수 수 변경 전/후, 최장 호출 경로, 재귀)를 handoff에 기록.

## 구조 기준 기록(변경 전, base_sha 기준 이름 있는 함수 수 / 전체 함수 노드 수)

runtime.ts 26/30(기존 초과), mainActions.ts 5/7, mainApprovals.ts 4/10, mainCheckpoint.ts 7/15, mainHandover.ts 7/11, mainTakeover.ts 5/5, mainRole.ts 4/10, executor.ts 77/125(기존 초과). onMainEnd 기준 최장 정적 경로 7회(runtime.ts approve → executor.ts approve → setStatus → event). 변경 후 값은 handoff에 기록한다.

## handoff

전체 커밋 SHA와 적용 순서, 변경 파일, 문제별 재현 테스트와 결과, 미검증, 리스크, 롤백을 최종 보고에 기록한다.
