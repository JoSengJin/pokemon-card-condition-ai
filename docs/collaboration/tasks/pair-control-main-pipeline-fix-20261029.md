# 작업 계약: pair-control 연속 관제 통합 검토 보완(P1 3 + P2 3)

- task_id: `pair-control-main-pipeline-fix-20261029`
- owner: Claude (구현)
- status: implementing
- base_sha: `be4ce92a0fbb09817e33c322db80ce5bf72abfd3` (전달받은 시작 SHA와 실제 HEAD가 같음을 확인. 이 worktree 미커밋 변경 없음, 진행 중 실행 없음)
- branch: `claude/pair-control` (기존 worktree 재사용)
- 통합·운영 push·실제 모델 호출: 하지 않음. push 검증은 임시 bare 원격만 쓴다. main 통합과 운영 push는 현재 메인이 한다.
- 근거(기본 checkout, 읽기 전용): `artifacts/pair-control-main-pipeline-review-20261029/`의 REPORT.md·repro.log·review-pipeline-repro.mts·structure.log, 선행 `artifacts/pair-control-main-safety-review-20261029/REPORT.md`, 기본 checkout의 현재 AGENTS.md·PAIR_CODING.md·docs/collaboration/HTML_REPORTING.md. 이 브랜치의 AGENTS.md/PAIR_CODING.md 사본은 낡았으므로 수정하지 않는다.
- 재현 스크립트는 근거로만 쓰고 제품 코드로 복사하지 않는다. 필요한 반례는 `test/review-fixes.test.ts` 등 회귀 테스트로 옮긴다.

## 완료 조건

### P1-A 공급자별 한도 구분
1. 한도 문구가 나온 출처 실행의 공급자(`main`·`agent`(worker) 실행의 agent)를 구분한다. 그 공급자만 `runtime.limited[agent]`에 기록하고, 그 공급자의 실행만 취소한다. 전역 `state.limit`·`cancelAll()`은 출처를 알 수 없거나(실행 기록 없음)·공급자 실행이 아닌 출처(`check`·`review`·기타)일 때만 보수적으로 유지한다. 과금 신호(`trip`)는 기존대로 전체 정지.
2. 같은 공급자의 한도는 그 공급자의 worker·메인·리뷰 시작과 교대 대상 모두를 막는다(다른 세션으로 우회 불가). 다른 공급자의 교대·실행은 막지 않는다.
3. 검증: Codex worker 한도→Claude 메인 인수 가능, Claude worker 한도→Codex 메인 인수 가능, 양쪽 한도→`blocked_both_limited`, 출처 불명→전역 차단 유지, 한도에 닿지 않은 공급자의 진행 중 worker 보존.

### P1-B 자동 push의 승인 범위
4. `push_main`은 `remoteHead..localHead`의 **모든 커밋**이 통합 승인된 작업의 통합 이력(`integration.preHead..newHead`)에 대응할 때만 수행한다. 알려진 작업이 하나 포함됐다는 이유로 전체 범위를 승인하지 않는다. 대응하지 않는 커밋이 하나라도 있으면 자동 push를 보류하고(원격 불변) 사용자가 기존 수동 push 경로로 직접 올린다. 모델·도구가 별도 범위 승인을 만들거나 추정하지 않으며, 이번 작업은 "사용자가 승인한 정확한 SHA 목록" 기능을 추가하지 않는다.
5. 검사는 `runPush`가 점검(preflight)·잠금·원격 재확인을 마친 **같은 계획**에 대해 실제 push 직전에 다시 수행한다(점검 후 HEAD·원격·승인 변경 재검사). push는 계획의 SHA를 명시해 실행하므로 이후 HEAD 변화는 반영되지 않는다.
6. 검증(임시 bare 원격): 승인 작업만 있는 성공 / 미등록 커밋 혼입 차단(원격 불변) / 푸시 결과 불명 뒤 재수행 차단 / 승인 철회 후 차단.

### P1-C 조건 미확정 시 자동 검사·모델 턴 보류
7. 승인 권한을 구분한다. ① **준비 권한**(`prepare_checks`, 신규 승인 행동 종류): 지정 검사 실행·인계 문서 생성만. ② **모델 턴 권한**: 이벤트의 다음 행동 종류(`confirm_handoff`/`approve_task`/`integrate_task`/`push_main`)에 대해 열린 승인이 있을 때만 턴을 시작. 어느 쪽도 다른 행동 승인으로 확대하지 않는다. 특히 `approve_task` 조건부 승인(`requires.handoffConfirmed`)은 준비 권한을 주지 않으며, 준비가 필요하면 사용자가 `prepare_checks`를 따로 기록해야 한다. 조건은 삭제·완화하지 않는다.
8. 열린 승인 = 철회 안 됨 + 세션 묶음 일치 + 저장소·브랜치·대상 일치 + **자유 문장 조건이 없음**. 자유 문장 조건이 있는 승인은 사람 판단 전 검사·인계·모델 턴 모두 0회로 보류하고 보류 사유를 기록한다. 구조화 조건(`requires`)은 행동 직전 기존대로 기계 검사한다.
9. `prepare_checks`는 모델이 제안할 수 있는 행동이 아니다(`ACTION_TYPES` 제외, 턴 요청문의 승인 행동 목록에서도 제외).
10. 검증: 조건 미확정이면 검사 0회·모델 턴 0회, 열린 승인 뒤 필요한 단계만 한 번. 기존 테스트의 "모델 턴이 끝난 뒤 행동만 거부" 기대를 수정한다.

### P2-D selfReview 승인 선택
11. `authorize`는 실행 맥락의 필수 조건(구현 에이전트=메인이면 `requires.selfReview` 필요)까지 충족하는 승인을 고른다(기록 순서 무관). 일반 승인만으로 자기 확인 불가, 철회·조건 미충족이면 거부. 자기 확인은 행동 결과·인계 메모에서 "독립 확인 아님"으로 구별 표시. 실제 운영 승인 장부에는 selfReview를 추가하지 않는다.

### P2-E 화면 연결
12. 관제 메인 패널(기존 화면)에 `pipelineView`를 연결해 표시한다: 메인 인수 상태·현재 턴, 개별 행동 결과, 보류·결과 불명 사유, 원격 push 검증을 마친 작업의 완료 상태. 새 대시보드·UI 프레임워크 없음(새 렌더 모듈 1개 + 기존 패널 호출 1줄 + 컨테이너 1개). API 객체 테스트와 별개로 로컬 브라우저(Playwright)로 실제 렌더를 확인하고, 열기 성공·렌더 확인·미확인을 구분해 보고한다.

### P2-F 구조 기준(최종 확정 해석)
13. 이름 없는 함수·화살표 콜백 포함 파일당 함수 정의 ≤7, 기존 Executor·체크포인트·push·교대로 이어지는 프로젝트 호출 포함 전이 ≤4. 이름 있는 함수만 세거나 담당 파일에서 끊어 세지 않는다. 사용자 승인 없는 예외 없음.
14. 이 수정이 건드리는 모든 소스 파일의 함수 수(전/후)와 시작 함수별 전이 수(전/후)를 `scripts/structure-trace.mjs`(`--all` 추가: 이름 일치 노이즈 제거·표준 메서드 제외·import 해석)로 측정해 기록한다. 동적 경로는 이름 일치 추정치를 확정값으로 쓰지 않고 실제 호출자와 대조한다.
15. 책임·호출 흐름 재설계(카운트 충족용 분할·콜백 인라인·책임 합치기·비동기 연결로 깊이 감추기 금지): 승인 원장/게이트/범위 분리, 행동 계획 분리, 턴 시작/종료 분리, 체크포인트 해시/구성 분리, 교대 인수 분리, `serialize(콜백)`을 잠금 획득(`lock`)으로 바꿔 콜백 경유 전이 제거, `revParse`→`run` 직접 호출, `audit`→`appendEvent` 직접 호출. 현재 기준 안에서 해결할 수 없는 경로(기존 Executor 내부 `approve`/`integrationState`/`runChecks`, `prepare.suggestTaskId`, `push.ts preflight/runPush` 등 이 작업이 재설계하지 않는 기존 모듈 내부 깊이)는 실제 경로·설계 대안·필요한 사용자 결정을 보고하고 그 경로의 채택만 보류한다.

### 계약 정합성
16. 기존 `executor.ts`의 stop 가드(`stopped`, `pipelineTick` 조기 반환)와 감독 프로세스 spawn 오류 처리(`sup.on('error')`)는 이 계약에 포함하고 비동기 경계를 회귀로 검증한다(stop 뒤 새 검사·턴 없음, spawn 오류가 프로세스 예외로 번지지 않고 감사 기록만 남음).
17. 재시작 복구 정책을 구분한다: ① **결과 불명 보존** — 서버 재시작 전 진행 중이던 턴·적용 중 행동(`launching`/`launched`(프로세스 없음)/`applying`)은 재실행하지 않고 `unknown`으로 남김. ② **검증 가능한 저장 응답의 최초 적용** — 재시작 시점에 이미 종료돼 있고 종료 기록·검증 가능한 응답이 저장된 `launched` 턴은 아직 적용 전이므로 같은 검사(세션·세대·토큰·확인·승인)를 통과하면 최초 1회 적용한다. 적용이 시작된(`applying`) 턴은 절대 재적용하지 않는다. 회귀 테스트와 README 단락으로 명시한다.
18. AGENTS.md/PAIR_CODING.md/HTML_REPORTING.md는 수정하지 않는다. 운영 Gemini fallback·학습·라벨·진척 배점·운영 `.state`·승인 장부 변경 없음.

## 허용 파일(정확한 목록)

- 신규(`tools/pair-control/src/executor/`): `limitScope.ts`, `approvalGate.ts`, `approvalScope.ts`, `actionPlan.ts`, `pipelineEnd.ts`, `pushOwnership.ts`, `mainAck.ts`, `checkpointBuild.ts`
- 신규(UI): `tools/pair-control/src/ui/js/view-pipeline.js`
- 수정(`tools/pair-control/src/executor/`): `executor.ts`(한도 위임·`cancelAll` 공급자 필터·`audit` 직접 기록·import, 함수 정의 수 증가 없음), `mainApprovals.ts`, `mainActions.ts`, `mainCheckpoint.ts`, `mainHandover.ts`, `mainDispatch.ts`, `mainEnd.ts`, `mainSerial.ts`, `mainTypes.ts`, `mainTakeover.ts`(요청문 승인 행동 목록·hash import 경로만), `pipelineEvents.ts`, `pipelineSteps.ts`, `pipelineTick.ts`, `pipelineTurn.ts`, `pipelineView.ts`, `turnBundle.ts`, `push.ts`(`runPush` 검증 훅 1개), `git.ts`(`revParse` 직접 `run`)
- 수정(기타): `tools/pair-control/src/runtime.ts`(공급자 한도 readiness·`push` 훅 전달·화면 요약), `tools/pair-control/src/ui/js/view-list.js`(패널 호출 1줄), `tools/pair-control/src/ui/page.html`(컨테이너 1개), `tools/pair-control/scripts/structure-trace.mjs`(측정 정확도·`--all`), `tools/pair-control/README.md`(정책 단락)
- 테스트: 신규 `test/review-fixes.test.ts`, `test/ui-pipeline.test.ts`; 기존 `test/pipeline.test.ts`·`test/nocharge.test.ts`·`test/main-safety.test.ts`·`test/main-rotation.test.ts`는 계약 변경으로 기대가 틀린 부분만 수정
- 문서: 이 계약, `docs/collaboration/reports/main-pipeline-fix-20261029.html`
- 범위 확대가 필요하면 이 계약을 먼저 갱신하고 커밋 메시지에 기록한다.
- 금지: `AGENTS.md`/`PAIR_CODING.md`/`HTML_REPORTING.md`, 데이터·라벨·모델·운영 코드, 기본 checkout, 운영 `.state`·승인 장부, 실제 Codex/Claude/Gemini 호출, 학습·사진 추론, 진척 배점.

## 검사

- 수정 전: 반례 회귀를 먼저 추가하고 수정 전 코드에서 실패하는지 확인해 기록한다.
- `npm run typecheck`; 관련 회귀(`review-fixes`·`pipeline`·`main-safety`·`main-rotation`·`nocharge`); `npm test` 전체. 모두 fake CLI·mock·임시 bare 원격이며 실제 CLI 검증이 아니다.
- 구조: `node scripts/structure-trace.mjs --all <src/executor/*.ts src/runtime.ts>` 변경 전/후 + 시작 함수별 실제 호출자 대조.
- HTML: 내용 대조, 로컬 열기, Playwright로 화면 렌더 확인(가능한 범위).

## structure (변경 전, 이름 포함 전체 함수 정의 수 / 이름 있는 것)

executor.ts 125/77(기존 초과), runtime.ts 32/28(기존 초과), push.ts 24/15(기존 초과), git.ts 19/11(기존 초과), mainApprovals.ts 18/6, mainCheckpoint.ts 16/7, mainHandover.ts 12/7, pipelineTurn.ts 10/6, pipelineView.ts 9/2, mainActions.ts 9/6, pipelineEvents.ts 6/4, pipelineSteps.ts 5/3, pipelineTick.ts 5/2, mainTakeover.ts 5/5, turnBundle.ts 4/4, mainDispatch.ts 3/3, mainSerial.ts 2/1, mainEnd.ts 1/1. 변경 후 값과 주요 호출 경로 전/후는 handoff에 기록한다. executor.ts·runtime.ts·push.ts·git.ts는 기존 초과 파일이며 이 작업은 함수 정의 수를 늘리지 않는 최소 수정만 한다(분리는 사용자 결정 필요 — 보고).

## HTML

`docs/collaboration/reports/main-pipeline-fix-20261029.html` — 생성·내용 대조·열기 요청 성공·렌더 확인을 handoff에 구분 기록한다. 합성 회귀 검사이며 모델 학습·추론·성능 평가는 하지 않았다.

## handoff

(작업 완료 시 채움: 전체 커밋 SHA와 적용 순서, 변경 파일, 구조 전/후, 검사 결과, 미검증, 리스크, 롤백)
