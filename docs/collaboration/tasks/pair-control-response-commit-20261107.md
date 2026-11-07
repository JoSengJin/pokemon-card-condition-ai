# 메인 응답 최종 반영 경계

- task_id: pair-control-response-commit-20261107
- owner: Codex
- status: ready_for_review
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

## 검증·인계

- 적용 순서: 기준819ca70bde57728e26b0c83507b318dc2853ad9b → 계약183f471eaf84f13b9ee6d4cf3632e40834f12bdc → 코드47a19fa99775e6910073d3d1d7f9820783c1ea21 → 이 문서/HTML 커밋.
- 변경: mainEnd/pipelineEnd가 await 뒤 현재 소유권·세대·상태와 한도를 재검사한다. main 인수는 stop/과금 가드도 확인한다. mark에 선택적 소유 턴 ID를 전달해 폐기/종료/적용/복구/준비 실패가 다른 턴의 이벤트를 덮지 못한다. README 및 합성 회귀 추가. 승인 판정/요청 실행/운영 상태 변경 없음.
- 최초 반례11개 중9실패·2정상. 추가 공통 이벤트 반례4개 중3실패·1정상. 최종 신규18개+기존 pipeline-apply5개+대표 fake CLI 파이프라인1개=24통과/0실패/0건너뜀. Git gate 대기 중 session/세대/stop/guard/limit 변경, 실패 응답, terminal 보존, 이벤트 새 소유권, 정상 응답, 저장/복구/최초1회 적용을 검증했다. 대표 파이프라인은 OS 프로세스 소유권 조회를 허용한 환경에서 fake CLI·임시 bare 원격만 사용했다.
- 타입/구조 검사 통과. mainEnd1→1, pipelineEnd2→2, pipelineState4→4, pipelineApply2→2, pipelineTick6→6, pipelineTurn4→4, 신규 테스트 익명 포함7. 전체270파일/786정의/최대7/최대전이4/초과0/순환0. monitorTick→onTurnEnd→verifyResponse→verifyAck→gitProcess.run=4, tick→pipelineTick→recoverTurns→mark→Store.save=4. 새 계층/경계/정의 없음.
- 원시 미확인93개 및 외부2747개 호출의 file/caller/call/reason 다중집합 불변. 기존 native 근거 중 pipelineTurn만 mark 인자 추가로 해시 변경, 실제 e.tried:number[] push는 불변 재검토. 나머지 근거 해시 동일. 출처 검토 뒤 미분류0은 동일 개발자 분류이며 독립 검토 아님. native-source-audit.json에 호출자·대상·실제 줄·근거·해시 보존.
- 로그/구조/출처 감사/테스트 정의 수: ignored artifacts/pair-control-response-commit-20261107/. 전체 npm test는 사용자 요청에 따라 재실행하지 않음. 과거 전체320개(319통과/1건너뜀, source8352bb51416836cd9e869bd4e7d88f88c1bade96)는 현재 소스 전체 검사로 주장하지 않음. 이번 핵심24건 건너뜀0, 과거 Playwright 미설치 자동 UI1건 미검증 유지.
- 리스크: 소유 미지정 legacy 이벤트는 기존 처리와 호환한다. 소유가 바뀐 이벤트는 보존하고 과거 턴만 stale/unknown/종료로 남긴다. 실제 CLI 수정 후 교대·계정 추가 사용/청구0·운영 배포는 미검증. 이번 실제 모델/학습/사진 추론0, 모델 성능 미평가. 카드분석 고정 장부 usable-card-analysis-v1.13 78/100은 별도이며 불변.
- 전체 요청 범위의 남은 코드 TODO를 새 기능으로 늘리지 않음. 이전 인수/배정/검토/승인/통합/push/중복/한도/복구/UI 수용 근거는 main-pipeline 계약과 기존 보고서에 보존. 이번 변경은 그 경계의 결함 보완. 실제 서비스 도입 완료/모든 실계정 동작 검증으로 보고하지 않는다.
- main 통합 대기: 확인 시 main에 다른 세션 surface-protocol-scope 미추적 문서3개와 개발 잠금이 있어 쓰기/통합/push하지 않음. 다른 세션 파일/잠금/프로세스는 보존. .claude/launch.json 해시 c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da 불변 확인. 준비 완료 뒤 main이 깨끗해지면 재확인·관련 통합 검사·일반 push.
- 롤백: 문서 커밋→코드47a19fa99775e6910073d3d1d7f9820783c1ea21→계약183f471eaf84f13b9ee6d4cf3632e40834f12bdc 순으로 git revert, 핵심 검사 후 일반 push. 실제 롤백 미실행. force/reset/.claude 수정/결과 불명 재실행 금지.

- HTML: IAB 열기·실제 렌더 확인 완료, report-render.png 보존. 검증 SHA/24통과/통합 대기 표시 대조. 등록 worktree9개(기본1+비기본8) 보존·제거0: 현재 앱 checkout/기본 저장소·미통합/미확인/고유 근거·기존 운영 서버 보호. Git SHA/status를 worktree-audit.json에 기록. 통합/원격 완료를 뜻하지 않음.
