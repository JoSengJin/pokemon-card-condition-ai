# 작업 계약: pair-control 구조 기준 준수 (한정 예외·동결 없음)

- task_id: `pair-control-structure-compliance-20261029`
- owner: Codex (Claude의 `93c1e2b81d4c682fcbaf530b5daf7771593264cd` 체크포인트에서 구현 인수)
- status: implementing (단계별 진행 — 아래 단계 완료 조건 참조)
- base_sha: `6857715afd87c0922d3e0e0510efce0435e156b6` (전달받은 최신 문서 커밋과 실제 HEAD 일치, 작업 트리 변경 없음. 검토 대상 코드 커밋 `0b3341cd8b7a5d3722af94790f79c2f8d0e000f7`)
- branch: `claude/pair-control` (기존 worktree). 통합·운영 push는 Codex. 실제 모델 호출·학습·사진 추론·운영 push 없음(fake CLI·스텁·임시 bare 원격만).
- 사용자 결정: **코딩 규칙 준수**. 한정 예외·기준 완화·기존 파일 동결안은 채택하지 않는다. 기본 checkout의 최신 PAIR_CODING.md §2.1을 그대로 적용한다(파일당 정의 ≤7 — 익명 콜백 포함, 호출 전이 ≤4 — 파일·객체·래퍼를 넘어 계산, 임의 경계 없음).
- 이 브랜치의 AGENTS.md/PAIR_CODING.md/HTML_REPORTING.md 사본은 낡았으므로 수정하지 않는다.

## 목표

tools/pair-control의 모든 소스(src/**, scripts/*.mjs)가 위 기준을 충족한다. 기능은 추가하지 않고 구조만 바꾼다. 지금 상태에서 충족을 주장하지 않는다 — 아래 현황과 단계로 진행하고 단계별로 측정 결과를 기록한다.

## 측정 도구 (단계 0, 완료)

`scripts/structure-trace.mjs`를 다시 만들었다: 이름 일치 추정 없음, 확정 간선만 계산(식별자·import·네임스페이스·this·타입 주석 체인·콜백 매개변수·수동 간선), 확정 못한 멤버 호출은 `unresolved`로 나열, `--check`는 초과 시 실패. 수동 간선은 `scripts/structure-edges.json`에 근거와 함께만 둔다. 회귀: `test/structure-trace.test.ts`(ops.push 오탐·verify 콜백·run.resume 오탐·함수 수·수동 간선 근거·실제 경로 pushNow 7회/onMainEnd 12회). 재현 명령: `node scripts/structure-trace.mjs > out.json`(저장소 기준 약 10초).
알려진 한계: getter 접근은 호출 전이로 세지 않음(함수 정의 수에는 포함), 타입 주석 없는 지역 변수·`ops`(MainOps)·Mastra 동적 호출은 수동 간선 또는 미확인, 이름 있는 시작 함수 + 프로젝트 함수에 넘긴 콜백만 시작점. 측정 도구 자체의 구조 준수는 단계 6에서 다룬다(현재 정의 45개 — 미준수).

## 현재 현황 (base 6857715, 도구 측정)

대상 73개 파일 중 **31개가 정의 7개 초과**, 호출 전이 4회 초과 시작 함수 **46개**(파일 18개), 확정하지 못한 멤버 호출(미확인) 253개.

### 파일별 함수 정의 수 (7 초과)
| 파일 | 정의 수 |
|---|---:|
| `src/executor/executor.ts` | 126 |
| `src/mastra/index.ts` | 60 |
| `scripts/structure-trace.mjs` | 46 |
| `src/runtime.ts` | 32 |
| `src/ui/js/view-list.js` | 25 |
| `src/executor/push.ts` | 24 |
| `src/executor/contract.ts` | 22 |
| `src/ui/js/logview.js` | 22 |
| `src/executor/prepare.ts` | 20 |
| `src/ui/js/form.js` | 20 |
| `src/executor/git.ts` | 19 |
| `src/ui/js/actions.js` | 17 |
| `src/ui/js/contract-request.js` | 16 |
| `src/executor/taskControl.ts` | 14 |
| `src/ui/js/panels-release.js` | 14 |
| `src/ui/js/panels-work.js` | 14 |
| `src/ui/js/stages.js` | 14 |
| `src/executor/logstream.ts` | 13 |
| `src/ui/js/events.js` | 13 |
| `src/ui/js/view-task.js` | 13 |
| `src/executor/nocharge.ts` | 12 |
| `scripts/start.mjs` | 11 |
| `src/executor/adapters.ts` | 11 |
| `src/executor/freeGuard.ts` | 11 |
| `src/executor/startPrompt.ts` | 11 |
| `src/ui/js/app.js` | 11 |
| `src/workflow.ts` | 11 |
| `src/executor/contractFile.ts` | 10 |
| `src/executor/mainRole.ts` | 10 |
| `src/executor/supervisor.mjs` | 10 |
| `src/ui/js/form-specs.js` | 8 |

### 호출 전이 4회 초과 시작 함수 (파일별 개수·최장·최장 시작점)
| 파일 | 초과 시작점 수 | 최장 | 최장 시작 함수 |
|---|---:|---:|---|
| `executor.ts` | 8 | 16 | `tick` |
| `mainEnd.ts` | 1 | 12 | `onMainEnd` |
| `mainAck.ts` | 1 | 11 | `ackSession` |
| `pipelineEnd.ts` | 1 | 11 | `onTurnEnd` |
| `mainActions.ts` | 2 | 10 | `applyActions` |
| `index.ts` | 12 | 9 | `buildRoutes` |
| `mainDispatch.ts` | 2 | 8 | `dispatch` |
| `pipelineTick.ts` | 1 | 8 | `pipelineTick` |
| `pipelineTurn.ts` | 2 | 7 | `handleLimit` |
| `structure-trace.mjs` | 2 | 6 | `trace` |
| `limitScope.ts` | 1 | 6 | `onLimitHit` |
| `mainHandover.ts` | 2 | 6 | `handoverMain` |
| `pipelineSteps.ts` | 1 | 6 | `autoSteps` |
| `runtime.ts` | 3 | 6 | `push` |
| `app.js` | 4 | 6 | `refresh` |
| `push.ts` | 1 | 5 | `runPush` |
| `taskControl.ts` | 1 | 5 | `createVenv` |
| `workflow.ts` | 1 | 5 | `execute` |

실제 호출자 근거가 확인된 대표 경로(Codex 대조와 일치): `pushNow → runtime.push → runPush → verify 콜백 → verifyPushScope → pushScope → commitsBetween → run` = 7, `onMainEnd → onTurnEnd → applyActions → runOne → dispatch → pushNow → …` = 12(수동 간선 근거: `scripts/structure-edges.json`).

## 설계 원칙 (카운트 충족용 편법 금지)
- 응집된 책임 단위로 파일을 나누고, 분리한 뒤 호출 경로를 다시 측정한다. 분리만으로 깊이가 줄었다고 보고하지 않는다.
- 책임 합치기·판정식 복제·불필요한 인라인·콜백/비동기 연결로 깊이 감추기 금지. 승인 대상·조건 판정은 `approvalGate` 단일 구현을 유지한다.
- 종료 라우팅·인수·행동 수행·한도 처리의 순서를 바꿀 때 기존 안전성 조건(세션·세대·승인·대상·현재 상태 재검사, 중복·철회·결과 불명 차단, 자유 문장 조건 보류, selfReview, push 범위·직전 재검사, stop 가드, 재시작 정책, 공급자별 한도)을 테스트로 보존한다.


## 반례 검토와 설계 원칙: 호출 프레임 예산 (코드 수정 전 확정)

문자 그대로 "모든 시작 함수 ≤4"를 적용한 반례 분석(도구 측정 근거): Git 실행 원시 함수 \`run\`까지의 최단 사슬이 이미 \`G.helper→run\`(1)·\`preflight→G.helper→run\`(2)·\`runPush→preflight→…\`(3)이라, 진입점 \`onMainEnd\`에서 \`run\`까지 프레임이 4개를 넘는다(현재 12회). 감시 사슬 \`tick→tickOnce→finalize→onAuxEnd→onMainEnd\`는 진입 전에 이미 4회를 쓴다. 따라서 "파일만 나누기"로는 충족할 수 없고, **프레임 예산을 정하고 흐름을 평탄하게 재설계**해야 한다(경계 선언으로 측정을 끊는 방식은 쓰지 않는다).

- **프레임 예산(모든 진입점 공통)**: L0 진입점(감시 틱·API·종료 처리) → L1 오케스트레이터(순서·상태 전환만) → L2 단계 함수(승인 검사·계획·결과 기록) → L3 서비스 함수(IO를 직접 호출, 헬퍼 층 없음) → L4 IO 원시(\`run\`·fs·저장). 각 함수는 자기 층 아래만 호출한다.
- **데이터를 넘기고 호출을 중첩하지 않는다**: 예) push — 오케스트레이터가 \`preflight(plan)\` → \`verifyPushScope(plan)\` → \`lockAndConfirm(plan)\` → 직전 승인 재검사(동기, 같은 \`authorize\`) → \`execPush(plan)\` 순으로 부른다. \`runPush\`가 \`preflight\`·콜백을 안쪽에서 부르는 중첩을 없애, push 직전 재검사·점검 후 HEAD 변경 안전성(현재 회귀 \`review-fixes\` B)은 단계 순서로 유지한다. 승인 판정은 \`approvalGate\` 단일 구현.
- **감시 사슬**: Executor 감시 루프는 "종료 관찰→기록"과 "관제 처리"를 같은 호출 스택에 두지 않고, 종료 관찰이 영속 상태(이미 있는 \`exit.json\`·task/turn 상태)를 갱신한 뒤 다음 틱의 관제 진입점이 상태를 읽어 처리하는 **상태 기계**로 재설계한다. 비동기 큐로 깊이를 감추지 않는다: 단계 사이의 인수인계는 영속 상태 전이이며 각 진입점은 자기 상태만 보고, 재시작 복구 정책(결과 불명 보존·검증된 저장 응답 최초 적용)을 그대로 따른다.
- **Executor 분리**(126 정의): 상태 저장·작업 수명주기·승인/통합·검사·실행 감독·한도·로그를 별도 모듈로, 공개 메서드는 L1~L3에 배치. 각 파일 ≤7.
- 위험: 종료 라우팅·인수·행동 수행·한도 순서 변경은 안전성 핵심 경로를 건드린다 → 각 단계 전에 해당 회귀(\`main-safety\`·\`pipeline\`·\`review-fixes\`)를 먼저 고정하고 단계 후 재실행.

## 단계와 완료 조건 (각 단계는 작은 커밋, 단계별 typecheck + 관련 회귀 + 구조 재측정)
0. 측정 도구·회귀·현황 고정(완료 — 이 계약과 함께).
1. 관제 코드(main*·pipeline*·approval*·limit*·push 소유권·체크포인트·UI 관제 패널): 호출 전이 ≤4(종료 라우팅·인수·행동 수행·한도·승인 범위·화면 요약). 완료 조건: 이 영역 시작 함수가 `--check`의 overStarts에 없음(수동 간선 포함).
2. 연결부·API: `runtime.ts`·`mastra/index.ts`·`workflow.ts` 분리(정의 ≤7, 깊이 ≤4).
3. Executor 분리: `executor.ts`를 책임별 모듈(상태·승인·통합·검사·실행·한도·감시·로그)로 분리(각 ≤7, 호출 ≤4), 감시 사슬 `tick→tickOnce→finalize→onAuxEnd` 재설계.
4. 나머지 실행기 파일(push·contract·prepare·git·taskControl·logstream·nocharge·adapters·startPrompt·freeGuard·mainRole·contractFile·supervisor).
5. 화면 모듈(ui/js 14개 파일).
6. 스크립트(start.mjs·structure-trace.mjs 자체).
7. 최종: `--check` 전체 통과, 미확인 253개 목록을 실제 호출자와 대조해 분류·보고, 전체 테스트, 화면 렌더 확인, HTML 보고서.
미완료 단계는 "준수 완료"로 보고하지 않는다. 요구사항 충돌이 실제로 남으면 해당 경로·반례·가능한 설계를 보고한다.

## 허용 파일 / 금지
- 허용: tools/pair-control/src/**, scripts/*.mjs, scripts/structure-edges.json, test/**(구조·측정·회귀), README.md, docs/collaboration/tasks/pair-control-structure-compliance-20261029.md, docs/collaboration/reports/pair-control-structure-compliance-20261029.html. Executor 등 선행 본체 포함.
- 금지: 기능 추가, 다른 프로젝트·모델·데이터·라벨 코드, 기본 checkout, 운영 `.state`·승인 장부, AGENTS.md/PAIR_CODING.md, 실제 CLI·모델 호출, 진척 배점.

## 검증 / 롤백
- 단계마다: `npm run typecheck`, `node scripts/structure-trace.mjs --check`(해당 영역), 관련 회귀. 최종: 전체 `npm test`를 `caffeinate -dimsu`로 실행(잠자기로 시계가 튄 실패는 기록하되 지우지 않음).
- 롤백: 단계별 커밋을 `git revert`(시작 SHA `6857715`로 복귀 가능).

## handoff
(최종 SHA·측정 전/후는 완료 시 보고서에 기록. 아래는 세션 체크포인트.)

### 체크포인트 (세션 한도 전 기록, 2026-10-29)
- 기준선(2228ede): typecheck 통과, `npm test` 180개 중 179 통과·0 실패·1 건너뜀(403초).
- `6f6af6b`: runPush→verifyPushScope 직접 간선 회귀(도구 `--start` 출력에 `callees` 추가), structure-edges.json evidence를 gate 직접 호출 구조로 정정. 자동 push의 gate 누락 경로는 기존 `review-fixes` B(승인 철회·미등록 커밋·점검 뒤 HEAD 변경)가 applyActions→dispatch→runtime.push→runPush 실경로로 검증한다.
- 단계 1b 일부(턴 경로 상태 기계): `onTurnEnd`는 검증 통과 응답을 `verified` + `pendingActions`로 저장하고 끝낸다. 적용은 `pipelineApply.applyVerified`(연속 처리 진입점)가 저장 상태를 읽어 `applying` 저장 → `applyActions`로 한다. 적용 직전 세션·세대·frozen 재확인, 정지 시 미적용, 재시작 뒤 이전 수명의 `verified`는 최초 1회 적용·`applying`은 결과 불명 보존. 회귀 `test/pipeline-apply.test.ts` 4개.
- **측정 결과: 구조 준수 아님.** 초과 파일 31개 불변, 초과 시작점 57→59(applyVerified·applyTurn 사슬 11~12가 새로 생김, onTurnEnd는 handleLimit 사슬 8). 이유: 행동 수행 사슬 `applyActions→runOne→dispatch→pushNow→runtime.push→runPush→preflight→done→save→writeJsonAtomic`(최소 9)이 그대로여서, 관찰/적용 분리만으로는 깊이가 줄지 않는다. 호출을 옮긴 것을 통과로 보고하지 않는다.

### 다음 실행 설계 (미착수)
깊이 ≤4가 성립하려면 진입점(L0)에서 IO 원시(L4)까지 프레임이 4개다: tick(L0)→pipelineTick(L1)→단계 함수(L2)→서비스(L3)→IO(L4). 따라서 (1) `MainOps` 간접층과 `pushNow`·`dispatch` 중첩을 없애고 행동별 단계 함수가 서비스를 직접 호출, (2) 행동을 `accepted→authorized→dispatching→done` 영속 단계로 나눠 각 단계 진입점이 저장 상태만 읽음, (3) push를 `plan→scope→lock→exec` 영속 단계로 분리(`preflight`는 git 사실 수집·스캔·판정으로 쪼갬), (4) `Store.save`가 원자적 쓰기를 직접 수행(현재 save→writeJsonAtomic 2프레임), (5) 세션 인수 경로(`ackSession`)에도 같은 verified/pendingActions 분리. 이후 단계 2~7은 계약 순서대로.
- 재개 명령: `cd tools/pair-control && npm run typecheck && node scripts/structure-trace.mjs --check`(현재 실패 예상), 전체 회귀 `caffeinate -dimsu npm test`.

### Codex 인수 체크포인트 (2026-10-29)
- 작업 브랜치/worktree: `codex/pair-control-structure-continuation-20261029`, Claude checkout은 변경하지 않고 보존했다.
- `1f781dc`: `Store.save`가 tmp 작성과 rename을 직접 수행한다. `store.ts` 정의 수 5→5, `save→writeJsonAtomic` 1회→`save` 0회. typecheck와 main-safety/pipeline-apply 16개 통과.
- `7e0e79e`: 공용 `dispatch→pushNow` 라우터를 없애고 `runOne`이 일반 행동 서비스와 `confirmAction`/`pushAction`을 직접 선택한다. 승인 판정은 `approvalGate.authorize` 단일 구현을 유지한다. `mainDispatch.ts` 정의 수 3→2, `runOne` 최장 8→7, `onMainEnd` 최장 11→10. typecheck와 structure-trace/main-safety/review-fixes 36개 통과.
- 현재 판정: **구조 준수 아님**. 초과 파일 31개, 미확인 81개이며 1b의 영속 행동 단계·push 단계·ackSession 분리와 단계 2~7은 남아 있다. 전체 테스트·최종 `--check`는 아직 실행하지 않았다. HTML 열기 요청은 queued였고 Mac 잠금·로컬 브라우저 비활성으로 실제 렌더 확인은 차단됐다.
- 다음 정확한 작업: 행동 `accepted→authorized→dispatching→done`을 저장 상태로 만들고 각 틱이 한 단계만 읽어 처리한다. 그 뒤 push `plan→scope→lock→exec`와 `ackSession`을 같은 방식으로 분리한다.

### Codex 단계 1b 후속 체크포인트 (2026-10-30)
- `7fb3895`: `ackSession`은 인수 확인 뒤 `taken_over + pendingActions`만 저장한다. 다음 감시 틱의 `applyTakenOver`가 `applying`을 먼저 저장하고 적용하며, 재시작 전 `applying` 세션은 결과 불명으로 보존한다. `ackSession` 호출 깊이 9→기준 이내(≤4).
- `eaa220e`: 행동을 `accepted→authorized→dispatching→done` 영속 상태로 분리했다. 세션·턴은 감시 틱마다 한 단계만 진행하고, dispatch 직전에 세션·세대·frozen·승인을 다시 검사한다. `dispatching` 재시작은 재실행하지 않는다. 승인 후 철회 반례는 서비스 호출 0회로 검증했다.
- `551aa7a`, `874afa1`: 자동 행동의 `MainOps.push→pushAction`과 `MainOps.confirm` 간접층을 제거했다. 자동 push는 `dispatchAction`이 `runPush(ex, sha, {sessionId})`를 직접 호출해 기존 push 직전 범위 재검사를 유지한다. 수동 간선은 6→3.
- 검증: Node 24.21.0에서 typecheck 통과. main/session/pipeline/rotation/safety/review-fixes 관련 42개 통과, push·review-fixes·structure 관련 34개 중 기대치 갱신 전 1건을 수정한 뒤 structure 6개 통과, 최종 confirm 변경 관련 27개 통과. 실제 CLI·모델·운영 push는 호출하지 않았고 합성 원격만 사용했다.
- 현재 측정: 초과 파일 31개, 초과 시작점 58개, 미확인 82개. **구조 준수 아님.** `dispatchAction` 최장 5(`runPush→preflight→git→netEnv→sanitizedChildEnv`), `advanceActions` 최장 6(`authorizeAction→plan→suggestTaskId→branchExists→git→run`), `pipelineTick` 최장 9. 전체 `npm test`와 최종 `--check`는 아직 실행하지 않았다.
- 다음 정확한 작업: push를 `plan→scope→lock→exec` 저장 단계로 분리하고 `preflight`의 사실 수집·스캔·판정을 나눈다. 이어 `actionPlan`의 assign 준비 조회 사슬과 한도 처리 `handleLimit→handoverMain→launchSession→launchMainProcess→realReadiness`을 평탄화해 단계 1 완료 조건을 재측정한다.
- `30a6ac6` 추가: push 네트워크 환경 래퍼(`netEnv`)와 `verifyPushScope→pushScope` 중첩을 제거했다. `runPush`가 사실 수집 결과를 직접 판정하고 동일한 `authorize` 구현으로 push 직전 승인 철회를 재검사한다. push 경로는 ≤4가 되었고 초과 시작점은 58→55. 승인 철회·미등록 커밋·점검 뒤 HEAD 변경·합성 원격 회귀는 유지됐다. 다만 `plan→scope→lock→exec`의 단계별 영속 상태와 preflight 파일 분리는 아직 남아 있다.
- `18f94ec`: 자동 push를 실제 `plan→scope→lock→exec` 저장 단계로 분리했다. scope의 소유 작업을 저장하고 잠금 뒤 exec 직전에 승인을 재검사한다. exec 상태 재시작은 원격 호출 없이 결과 불명으로 보존한다. `a042657`은 런타임에서 쓰지 않던 테스트 호환 `applyActions` 루프를 제거했다.
- `622e682`, `524081c`: task ID 브랜치 조회와 승인 스냅샷 Git 조회·상태 이벤트 저장의 단순 래퍼를 제거했다. 현재 측정은 초과 파일 31개, 초과 시작점 49개, 미확인 83개이며 `dispatchAction`·`authorizeAction`은 ≤4다. 관련 파이프라인 회귀 58개, 준비·안전·구조 회귀 21개와 최종 구조 회귀 6개가 통과했다. 다음 병목은 `pipelineTick→applyVerified→applyTurn→advanceActions→advancePushAction→preparePush→preflight`와 한도 인수 사슬이다.


### Codex 실행기·화면 분리 체크포인트 (2026-11-05)
- 단계 커밋: ed6b423 Git 조회·작업 준비·로그·감독 IO 분리, 284c962 push 점검과 턴 실행 요청의 영속 단계.
- 실행기 함수 정의(이번 묶음 전→후): git 19→0(facade), mainRole 10→2, logstream 13→0(facade), supervisor 10→6, prepare 20→0(facade), push 28→0(facade). 분리된 실행기 파일도 모두 ≤7로 측정했다.
- 자동 push는 plan→facts→scan→check→scope→lock→exec 저장 단계다. facts는 Git 사실, scan은 커밋 전체 이력, check는 오탐 판정·dry-run, scope/exec는 같은 approvalGate 승인을 대조한다. 실행 감시가 저장된 행동을 직접 수행하고 같은 단계에서 부모 턴 결과도 마감한다.
- 새 모델 턴은 queued 요청을 저장한 뒤 실행 감시가 launching을 먼저 저장한다. 실제 턴 ID가 생기면 요청과 연결한다. queued의 최초 재개, launching 결과 불명 보존, 이미 저장된 턴의 종료 상태 보존, 실행 전 승인 철회·stop을 회귀로 검증했다.
- UI 함수 정의(전→현재 facade 또는 진입점): actions 17→0, app 11→3, contract-request 16→0, events 13→0, form-specs 8→0, form 20→0, logview 22→0, panels-release 14→0, panels-work 14→0, stages 14→0, view-list 25→0, view-task 13→0. 각 실제 구현 파일도 ≤7이다. 카드의 단계 계산과 HTML 렌더를 호출자가 순서대로 수행해 중첩을 줄였다.
- 검증: typecheck 통과. Git·로그·감독·메인 관련 23개, prepare 3개, push·범위·상태 적용·구조 46개 통과. 감시 라우팅 후 교대 양방향 통합 2개, 턴 요청 재시작 4개 통과. UI·contract 25개 중 24 통과·1 건너뜀, contract-handoff 7개 통과. 부모 턴 완료가 push보다 한 틱 늦던 회귀는 수정 후 양방향 통합과 push 단일 회귀로 재확인했다.
- 브라우저: 합성 snapshot을 제공하는 읽기 전용 localhost 미리보기에서 작업 목록·상세·교대 후 연속 처리 패널을 실제 확인했다. 최종 소스 재로딩 뒤 오류·경고 로그 없음. screenshot은 로컬 검증 증거로 보존한다. Playwright 기반 자동 브라우저 항목은 설치 부재로 여전히 건너뜀이며, 수동 렌더 관찰과 구분한다.
- 현재 정적 측정: 초과 파일 2개(start 11, structure-trace 69), 초과 시작점 5개(모두 structure-trace 내부), 미확인 호출 101개. **전체 구조 준수 아님.** MainOps의 남은 3개 간접 호출, API·workflow 동적 연결, 외부 분류의 실제 근거 대조와 콜백 호출 전이 검증이 남았다. 측정 도구 자체도 분리·평탄화해야 한다.
- 미완료 검증: 이 체크포인트 소스 전체 npm test, 최종 --check, 최종 HTML 보고서. 앞선 Executor 전체 회귀의 191개 중 1개 실패 기록은 보존하며, 해당 재시작 사례 수정·개별 통과를 전체 통과로 바꾸어 보고하지 않는다.
- 리스크: 감시 단계 순서·서버 재시작 정책·브라우저 모듈 연결. 단계별 git revert로 되돌리며 의존 커밋은 역순으로 복원한다. 운영 상태·모델·라벨·실제 모델 요청·main 통합·운영 push는 변경하지 않았다.
