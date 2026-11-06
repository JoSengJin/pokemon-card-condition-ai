# 관제도구 메인 턴 실행 직전 상태 검증

- task_id: pair-control-turn-start-20261106
- owner: Codex
- status: implementing
- base_sha: 9e58aa28d113cc3802484c343f9b39916dcd0f57
- branch: codex/pair-control-turn-start-20261106
- goal: 준비 대기 중 메인 세션/세대/동결/승인/대상 상태가 바뀌면 오래된 메인 턴을 실행하지 않고, 실행하지 않은 독립 작업은 최신 유효 상태에서 이어가게 한다.
- allowed_files: tools/pair-control/src/executor/pipelineTurn.ts, tools/pair-control/src/executor/pipelineEvents.ts, tools/pair-control/src/executor/monitorTick.ts, tools/pair-control/src/executor/verificationStart.ts, tools/pair-control/src/executor/verificationLifecycle.ts, tools/pair-control/test/verification-stop.test.ts, tools/pair-control/test/pipeline-start.test.ts, tools/pair-control/test/pipeline-launch.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-turn-start-20261106.html.
- forbidden_files: .claude/·운영 설정/상태/장부·모델/worker·사진/라벨/진척·다른 checkout/서버. 실제 모델 요청·학습·추론 금지.
- contract: 기존 approvalGate/turnHold의 단일 승인 판정과 기존 이벤트 생성 조건을 재사용. 세션/세대 변경은 stale로 보존, 철회/현재 대상 불일치는 해당 이벤트만 보류. 아직 실행하지 않은 유효 이벤트는 같은 세대에서도 최초 실행 가능해야 하며 실제 시작/결과 불명 요청은 재시도하지 않음.
- structure: 시작270파일/781정의/최대7·실제전이4. 함수 추가로 책임 숨기기·예외 경계 추가 금지. 변경 전후 파일별 정의·경로 및 원시 미확인/외부 호출 근거 대조.
- checks: fake CLI probe 대기 재현 → 관련 회귀·typecheck·structure --check → 전체 회귀(임시 bare 포함) → main 관련 검증·일반 push·원격 SHA 대조. HTML 생성·실제 렌더, .claude 해시·worktree 보존 기록.
- experiment: 없음. 실제 모델 호출0 유지.
- rollback: 후속 문서부터 역순 git revert·관련 검사·일반 push. 운영 장부 삭제/결과 불명 재실행 금지.

## 완료 감사 범위
- 메인 턴 준비 중 세션/세대/동결 변경, 승인 철회/조건 변경, 현재 작업 상태/SHA 변경, 혼합 이벤트의 독립 처리, stop/한도/무료 가드, 중복/재시작 결과 불명, 기존 양방향 교대·통합·push 회귀를 차례로 확인한다. UI 표시 보완 한 건이나 작은 커밋 완료를 세션 종료 기준으로 삼지 않는다.

## 실행 안전성 범위 보완
- runChecks는 준비 await 후 stop/guard를 다시 보지 않고 새 검사 기록·감시를 등록한다. startNextCheck와 monitorTick의 다음 검사 분기도 stop을 보지 않아 대기하던 검사를 시작할 수 있다. 검사를 새로 등록/시작하는 경계에 같은 중단 조건을 적용하고, 기존 실행의 종료 관찰·결과 불명 보존은 유지한다. 허용 파일에 이 경로와 합성 반례를 추가한 뒤 수정한다.
