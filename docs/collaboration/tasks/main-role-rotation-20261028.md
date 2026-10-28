# 작업 계약: 메인 역할 교대 실행(pair-control)

- task_id: `main-role-rotation-20261028`
- owner: Claude (구현) / 요청: 메인(Codex)
- branch: `claude/pair-control` (기존 worktree)
- 시작 HEAD: `ea0945d`
- 통합·push: 이 작업에서 하지 않음(현재 메인이 검토 후 처리)

## 목표

메인(Codex↔Claude)이 한도 소진 등으로 바뀔 때 표시·인계문만 바꾸지 않고, 저장된 체크포인트로 **새 메인 프로세스를 실제로 실행**해 인수 확인을 거친 뒤 승인 범위 안의 다음 행동을 수행하게 한다. 이전 메인의 지연 응답·중복 명령은 세대(generation)로 차단한다.

## 완료 조건

1. 양방향(Codex→Claude, Claude→Codex) 교대가 fake CLI로 실행되고, 새 메인이 체크포인트와 실제 Git 상태를 대조(인수 확인)한 뒤에만 메인이 바뀐다.
2. 승인 장부(approvals)에 기록된 범위 안의 행동만 수행하고 범위 밖(실험·force push·이력 재작성·승인 확대·다른 작업)은 차단한다. 세션에 묶인 승인은 승계하지 않는다.
3. 이전 메인의 지연 결과와 중복 행동 ID를 차단한다(세대·세션·행동 ID).
4. 한도 오류 직후 마지막 인계문 없이 저장된 체크포인트로 교대한다. 진행 중 구현 에이전트는 중단하지 않고 인수한다.
5. 결과 불명 실행·push는 확인 전 재실행하지 않는다.
6. 대상 메인 실행 실패·양쪽 한도 소진 시 상태와 복구 지점을 보존하고 재시도 루프를 돌지 않는다.
7. "역할 이양 완료"는 인수 확인과 다음 행동 수행 근거가 있을 때만 표시한다.

## 허용 파일

- `tools/pair-control/src/executor/main*.ts` (신규·수정), `executor.ts`, `adapters.ts`(필요 시), `tools/pair-control/src/mastra/index.ts`, `tools/pair-control/src/runtime.ts`
- `tools/pair-control/src/ui/` (메인 패널), `tools/pair-control/test/` (신규 테스트·fake CLI), `tools/pair-control/README.md`
- `AGENTS.md`, `PAIR_CODING.md` ("현재 메인" 중심 문구 정리, 데이터·실험·라벨 보호 규칙 유지)
- `docs/collaboration/reports/main-role-rotation-20261028.html`(HTML 보고), 이 계약 문서

금지: 데이터·라벨·모델·운영 코드, 실제 Codex/Claude/Gemini 호출, 실제 학습·사진 추론·라벨 수정·push, main 통합.

## 검사

- `npm run typecheck`, `npm test`(전체), 새 흐름 테스트(fake CLI)
- 새 파일은 파일당 함수 7개·호출 전이 4회 이하(PAIR_CODING 기준)를 지킨다. 기존 executor.ts 등은 줄 수 증가를 최소화한다.

## 미확인(구현에서 추정하지 않음)

실제 codex/claude CLI의 세션 재개·도구·권한 동작, 실제 한도 오류 문구 전체, 잔량 정보 제공 여부. mock에서 확인한 것과 구분해 보고한다.
