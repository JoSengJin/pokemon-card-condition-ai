# 메인 응답 최종 반영 경계

- task_id: pair-control-response-commit-20261107
- owner: Codex
- status: implementing
- base_sha: 819ca70bde57728e26b0c83507b318dc2853ad9b
- branch: codex/pair-control-response-commit-20261107
- goal: Git 인수 확인 await 뒤 현재 세션/세대/정지/가드/한도를 재확인하고, 이전 턴 종료가 새 턴 소유 이벤트를 되돌리지 않게 한다.
- allowed_files: tools/pair-control/src/executor/mainEnd.ts, tools/pair-control/src/executor/pipelineEnd.ts, tools/pair-control/src/executor/pipelineState.ts, tools/pair-control/src/executor/pipelineApply.ts, tools/pair-control/src/executor/pipelineTick.ts, tools/pair-control/src/executor/pipelineTurn.ts, tools/pair-control/test/response-commit.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-response-commit-20261107.html, ignored artifacts/pair-control-response-commit-20261107/.
- forbidden: 실제 모델/CLI/API 호출·학습·추론·운영 서버/상태·다른 작업/잠금·.claude/·사진/라벨/모델.
- contract: 인수 관찰과 행동 적용의 저장 상태 분리를 유지한다. 새 세션/세대의 역할과 이벤트는 과거 응답의 성공/실패 어느 쪽으로도 덮지 않음. 이미 불명/종료된 턴은 부활시키지 않음. 본인 소유(또는 아직 소유가 지정되지 않은 기존 기록) 이벤트만 endTurn이 갱신. 승인 판정식은 변경하지 않음.
- structure: mainEnd1/pipelineEnd2/pipelineState4 정의 불변, 실제 호출 전이4 이내. 새 경계/콜백 은폐 없음.
- checks: 합성 응답·임시 Git gate 반례와 정상 반영 → 필요한 기존 인수/연속 처리만 선별 → 타입/구조·출처 대조 → main 소스 동일성·일반 push·HTML 렌더. 전체 회귀/실제 모델 재실행 금지.
- risks: 준비 중 바뀐 응답은 적용 대신 stale/기존 종료 상태 보존. 본인 소유 이벤트는 기존 재판단 정책을 따르며 이미 시작/불명 요청은 재시도하지 않음.
- rollback: 관련 커밋 역순 git revert·핵심 검사·일반 push. force/reset·운영 상태 삭제 없음.

- scope_update: 호출자 대조에서 verified 폐기·적용 종료·재시작 복구·턴 준비 실패도 같은 이벤트 소유권 문제를 공유함을 확인. mark의 선택적 owner 인자로 공통 차단하고 모든 턴별 호출자에 현재 turn.id를 전달한다. 함수 수/깊이를 늘리지 않으며 소유 미지정 기존 기록은 호환한다. 신규 회귀에서 늦은 적용/복구도 새 소유 이벤트를 보존한다.
