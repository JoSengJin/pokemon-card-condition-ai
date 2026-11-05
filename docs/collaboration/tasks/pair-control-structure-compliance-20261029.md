# 작업 계약: pair-control 구조 기준 준수 (한정 예외·동결 없음)

- task_id: `pair-control-structure-compliance-20261029`
- owner: Codex (Claude의 `93c1e2b81d4c682fcbaf530b5daf7771593264cd` 체크포인트에서 구현 인수)
- status: integrated (2026-11-06 main 재검증·일반 push 완료 — 후속 main 채택 기록 참조)
- base_sha: `6857715afd87c0922d3e0e0510efce0435e156b6` (전달받은 최신 문서 커밋과 실제 HEAD 일치, 작업 트리 변경 없음. 검토 대상 코드 커밋 `0b3341cd8b7a5d3722af94790f79c2f8d0e000f7`)
- branch: `codex/pair-control-structure-continuation-20261029` (원래 `claude/pair-control` 체크포인트에서 인수한 분리 worktree). 통합·운영 push는 Codex. 실제 모델 호출·학습·사진 추론·운영 push 없음(fake CLI·스텁·임시 bare 원격만).
- 사용자 결정: **코딩 규칙 준수**. 한정 예외·기준 완화·기존 파일 동결안은 채택하지 않는다. 기본 checkout의 최신 PAIR_CODING.md §2.1을 그대로 적용한다(파일당 정의 ≤7 — 익명 콜백 포함, 호출 전이 ≤4 — 파일·객체·래퍼를 넘어 계산, 임의 경계 없음).
- 이 브랜치의 AGENTS.md/PAIR_CODING.md/HTML_REPORTING.md 사본은 낡았으므로 수정하지 않는다.

## 목표

tools/pair-control의 모든 소스(src/**, scripts/*.mjs)가 위 기준을 충족한다. 기능은 추가하지 않고 구조만 바꾼다. 아래 시작 현황과 단계별 기록을 보존하며, 최종 판정은 문서 끝의 최종 인계와 HTML 보고서를 따른다.

## 측정 도구 (단계 0, 완료)

`scripts/structure-trace.mjs`를 다시 만들었다: 이름 일치 추정 없음, 확정 간선만 계산(식별자·import·네임스페이스·this·타입 주석 체인·콜백 매개변수·수동 간선), 확정 못한 멤버 호출은 `unresolved`로 나열, `--check`는 초과 시 실패. 수동 간선은 `scripts/structure-edges.json`에 근거와 함께만 둔다. 회귀: `test/structure-trace.test.ts`(ops.push 오탐·verify 콜백·run.resume 오탐·함수 수·수동 간선 근거·실제 경로 pushNow 7회/onMainEnd 12회). 재현 명령: `node scripts/structure-trace.mjs > out.json`(저장소 기준 약 10초).
단계 0 당시 한계(현재는 아래 보완·최종 감사로 해소/분류): getter 접근은 호출 전이로 세지 않음(함수 정의 수에는 포함), 타입 주석 없는 지역 변수·`ops`(MainOps)·Mastra 동적 호출은 수동 간선 또는 미확인, 이름 있는 시작 함수 + 프로젝트 함수에 넘긴 콜백만 시작점. 측정 도구 자체의 구조 준수는 단계 6에서 다룬다(현재 정의 45개 — 미준수).

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

### Codex 측정기 보완 체크포인트 (2026-11-05)
- structure-trace의 기존 69개 정의를 파싱·선언/타입 색인·호출 수집/해석·그래프·깊이 계산·출력으로 분리했다. AST 순회와 최장 경로 계산은 반복문이며 호출 순환을 별도 보고한다. 정적 상한이나 재귀 생략으로 통과시키지 않는다.
- 익명 함수를 모두 시작점으로 측정하고 Array/Promise 등의 실제 동기 콜백 전이, 반환된 HTTP 래퍼가 호출하는 실제 handler, getter 읽기를 추가했다. 객체의 함수 속성 이름을 렉시컬 변수로 오인하던 순환 오탐도 고쳤다. promisify는 감싼 함수의 출처를 대조하며 프로젝트 함수를 외부로 제외하지 않는다.
- 보완 직후 초과 시작점 69개가 새로 드러났다. 명령 IO를 Node 표준 promisify로 정리하고, 환경·범위·상태 검사와 UI 표현의 불필요한 콜백 중첩을 반복 순회로 바꿨다. 체크포인트 구성/정규화/해시/저장, HTTP 인자 해석/서비스 수행, UI 데이터/패널/로그 렌더는 호출자가 데이터를 넘기며 순서대로 수행한다. 승인 판정식은 approvalGate 단일 구현 그대로다.
- 현재 정적 --check는 초과 파일 0·초과 시작점 0·호출 순환 0으로 통과했다. 단, 동적 호출과 외부 제외의 실제 출처 대조가 남아 있으므로 전체 구조 준수 완료가 아니다. 남은 MainOps 3개 및 프로젝트 콜백을 연결해 다시 측정해야 한다.
- 검증: typecheck 통과. 관련 64개 중 63 통과·브라우저 자동 검사 1 건너뜀, 측정기/명령 IO/JSON 정규화/로그 16개 통과, 최종 관련 62개 중 61 통과·같은 브라우저 자동 검사 1 건너뜀. key 순서·날짜·undefined·NaN·__proto__ 정규화, 명령 성공/종료코드/환경/spawn 실패/시간 초과, HTTP 인자 해석과 오류 응답을 회귀로 확인했다.
- UI 소스 재로딩 뒤 작업 목록·상세·교대 패널과 구현 단계 로그 창 전환을 브라우저에서 확인했다. 오류·경고 없음. 합성 GET 전용 서버이며 운영 상태 변경·실제 모델 호출은 없다.
- 다음은 미확인/외부 목록을 실제 선언·호출자와 대조하고 필요한 프로젝트 간선을 연결하는 단계다. 최종 전체 회귀·HTML 보고서는 아직 미완료다. 원격 통합·push도 하지 않았다.

### Codex 실제 연결 감사 체크포인트 (2026-11-06)
- MainOps 인터페이스·runtimeBind의 approve/integrate/assign 래퍼·수동 간선 3개를 제거했다. 행동 진입점은 승인 서비스·준비 서비스·실제 workflow 재개 서비스를 직접 호출한다. 승인 판정은 approvalGate 단일 구현이다.
- 반환 객체 메서드·팩터리 반환 리스너·생성자 함수 필드·옵션 객체 콜백·콜백 재전달·zod 중첩 validator를 실제 초기화/전달 근거로 추적한다. 측정기 회귀 17개 통과.
- 과금·한도 감지는 즉시 차단 상태와 취소 요청을 함께 저장하고, 감시 진입점이 pending→dispatching→sent로 그룹 취소를 수행한다. dispatching 재시작은 unknown으로 보존한다. 관련 안전성·상태 적용·취소 회귀 37개 통과.
- 전체 회귀: Node 24.21.0, caffeinate -dimsu npm test, 총 214개·213 통과·실패 0·기존 브라우저 자동 검사 1 건너뜀, 715151ms. 로그: /tmp/pair-full-regression-20261106.log (로컬). typecheck 통과. 검증 소스는 6bf2c29 이후 이 체크포인트의 작업 변경이며 문서와 공백 정리는 검증 후다.
- 현재 자동 그래프는 초과 파일 0·초과 시작점 0, 미확인 108·외부 분류 호출 지점 2676이다. 그러나 설치된 Mastra의 resolve-agent-CMSnjTVM.js:1414가 entry.step.execute를 실제 호출함을 대조했고, workflow.ts 조립을 따라 dispatchAction→startTask→launch execute→launch→spawnExec→setStatus→save (6회)가 남아 있음을 확인했다. 자동 그래프의 0을 전체 준수로 보고하지 않는다.
- 시작 SHA 6857715도 같은 측정기로 정의 수를 재측정해 초과 파일 31개를 확인했다. workflow 연결을 포함하지 않은 호출 깊이는 전후 준수 비교 근거로 쓰지 않는다. 다음은 workflow 요청·도메인 실행의 저장 상태 인계와 실제 framework 간선 연결, 미확인/외부 분류 감사, 변경 뒤 전체 재검증·HTML 보고서다. main 통합·운영 push·실제 모델 호출 없음. 롤백은 의존 커밋 역순 git revert.

### Codex workflow 영속 요청 체크포인트 (2026-11-06)
- workflowRequests와 serviceRequests를 JSON 상태로 나눴다. API·관찰·행동은 요청과 결과만 읽고, workflowTick은 저장된 native start/resume, serviceTick은 저장된 도메인 효과 하나를 직접 수행한다. 둘 다 queued→dispatching→done/failed, dispatching 재시작은 unknown이며 재호출하지 않는다. 서비스는 현재 수명의 부모 요청이 있어야 한다.
- 메인 행동의 세션·세대·수명·행동·대상·SHA를 요청에 저장하고 양쪽 실행 직전에 같은 approvalGate로 재승인한다. stop은 새 실행을 막는다. AsyncLocalStorage와 실행기별 Mastra 참조로 다른 실행기 초기화가 진행 중 요청의 대상을 바꾸지 못하게 했다.
- Mastra 실제 콜백 8개와 HTTP 인자 배열 서비스 3개를 근거 있는 간선으로 연결했다. 초과 파일·시작점·순환은 0이다. 미확인 88개는 미분류 상태이므로 전체 준수 완료가 아니다. 특히 Hono compose.js:35의 next→handler도 대조 중이며 외부로 무조건 제외하지 않는다.
- 검증: typecheck 통과. 저장 요청·승인 철회·세대 변경·stop·결과 불명·실행기 격리 및 측정기 24개 통과. 실행기·안전성·교대·파이프라인·승인 취소 관련 37개 통과(339582ms). 양방향 합성 원격 push 포함, 실제 모델·운영 원격 호출 없음. 전체 214개 회귀 통과는 직전 4905314 소스의 결과이며 이번 요청 구조의 전체 회귀는 아직 아니다.
- 리스크: 요청 장부 추가와 worker 타이머 수명, workflow 재개 순서. stop은 두 worker 타이머도 정리한다. 결과 불명은 보수적으로 보존하며 자동 재시도하지 않는다. 롤백은 이 단계 커밋 git revert이며 저장된 결과 불명 기록은 임의 삭제하지 않는다.

### HTTP 정책 연결 정리의 허용 범위 보완 (2026-11-06)
- tools/pair-control/package.json 및 package-lock.json을 추가 허용한다. 이미 Mastra 의존성으로 설치·잠금된 Hono 4.13.13의 validator를 직접 사용할 때 같은 버전을 직접 의존성에 명시하는 데 한정한다. 버전 변경·추가 다운로드·새 서버 기능은 없다.
- Hono compose의 프로젝트 middleware→next→route 중첩을 실제 대조했다. host/origin/x-pair-control 정책은 독립 검증 콜백이 Response 또는 승인 결과를 반환하도록 하고, Hono의 기존 validator가 그 결과를 확인한 뒤 next를 호출한다. 프로젝트 검증 콜백이 다음 handler를 호출하는 사슬은 제거하며 정책은 그대로 유지한다. validator.js의 validationFunc 반환 확인→next 순서와 HTTP 허용/거절 회귀로 검증한다.

### Codex HTTP 정책·실행 직전 반례 보완 (2026-11-06)
- Hono 4.13.13 기존 설치 버전을 직접 의존성에 명시했다(잠긴 패키지 버전·다운로드 변경 없음). validator의 검증 결과 확인 후 next 호출 순서를 사용한다. 프로젝트 validateRequest는 host/origin/x-pair-control 검사 결과만 반환하며 다음 라우트를 부르지 않는다. 이전 정책의 허용·거절 9개 사례를 실제 Hono 메모리 요청으로 검증했다.
- workflow createRun 대기 뒤에도 실행 직전 같은 승인 판정을 재검사한다. 재검토 runId·이력을 native 실행 전에 저장해 재시작 중 이전 runId로 연결되는 창을 없앴다. 서비스 완료 결과는 structuredClone 스냅샷으로 저장해 이후 task 변경과 공유하지 않는다.
- 측정기는 함수 값을 Array.push/Map.set에 보관하는 경우를 실행으로 오인하지 않게 했고, ??= 배열 기본값만으로 기존 프로젝트 객체를 제외하던 판정을 제거했다. 파생 refine 스키마도 원본·import·중첩 참조를 따라 검증 콜백에 연결한다.
- 검증: typecheck 통과, HTTP·저장 요청·실행 직전 철회·run 소유권·스냅샷 12개 통과, 측정기 21개 통과. 추가 검사 첫 명령은 뒤쪽 node에 PATH 설정이 이어지지 않아 Node18 환경 오류가 났고 해당 로그를 보존했다. Node24 명령으로 다시 실행한 12개가 실제 통과 근거다.
- 정적 --check 초과 파일 0·시작점 0·순환 0, 원시 미확인 86·외부 호출 지점 2730. 미확인 목록의 native Array/Set·Promise resolve·Hono context·Mastra 상태 기록·zod issue 기록 출처를 대조 중이며 최종 HTML에 호출 지점별 근거를 담는다. 이 단계 이후 전체 회귀와 최종 렌더는 아직 미완료다.

### 최종 인계 — 리팩토링 단계 0~7 완료 (2026-11-06)
- 검증 코드 전체 SHA: `6eddfd41934cf6452ee33d550016e1ffdd19810d`. 이 뒤의 변경은 이 작업 계약과 정적 HTML 보고서뿐이다. main 통합·운영 push는 실행하지 않았다.
- 고정 계약의 8개 단계(0~7) 완료. 모든 소스 270개 파일·함수 정의 779개(시작 SHA의 같은 AST 재측정: 73파일·797정의). 파일당 최대 7, 실제 프로젝트 호출 전이 최대 4, 초과 파일·시작점·순환 모두 0. 테스트 파일은 원래 계약의 회귀 범위이며 정의 수 측정 범위는 src/**·scripts/*.mjs 그대로다.
- 원시 미확인 86개는 출력에서 숨기지 않았다. 실제 호출자/초기화/타입/설치 라이브러리 대조 결과 Array/Set 53, Promise resolve 4, Hono Context 7, Zod issue 7, Mastra 상태 기록 13·조립 2다. 대조 뒤 미분류 0. 외부 호출 2730개(사유 370종)도 전체 지점·사유를 보고서에 보존했다. 실제 프로젝트 callback 간선은 측정에 포함했다. native 분류는 프로젝트 말단 예외나 임의 경계로 등록하지 않았다. 이 SHA에 한정한 동일 개발자의 소스 감사이며 독립 리뷰를 뜻하지 않는다.
- 최종 검증: `npm run typecheck` 통과(Node 24.21.0), `node scripts/structure-trace.mjs --check` 종료 0, `caffeinate -dimsu npm test` 총 228·227 통과·실패 0·취소 0·기존 브라우저 자동 검사 1 건너뜀, 756903ms. 최종 그래프가 감사한 그래프와 동일함을 대조했다.
- 전체 로그: 검사 세션 로컬 `/tmp/pair-final-full-regression-20261106.log`, SHA-256 `cffe9a19547160d3a360d5d941b7755460de9a162501b5df18a8e4508ef1e873`. 이전 실패·환경 오류 로그는 보존했고 최종 통과와 구분했다. 남은 실패 0, 구조 초과 0, 자동 브라우저 건너뜀 1(Playwright 미설치). 수동 렌더 관찰을 자동 테스트 통과로 바꾸지 않았다.
- 화면 확인: 최종 소스의 GET 전용 합성 localhost에서 작업 목록·교대 패널·보류/결과 불명·구현 로그 창을 실제 확인했고 오류·경고 로그 없음. 스크린샷 `pair-final-ui-20261106.png`(로컬 /tmp), SHA-256 `ab7694ecd906d224c85f81ff97d2c982d3fb086ba2e64d9463f6e18e7b11a9ad`.
- HTML: `docs/collaboration/reports/pair-control-structure-compliance-20261029.html`을 실제 브라우저에서 열고 렌더 확인했다. 첫 화면의 SHA·정의 수·전체 테스트 결과를 대조하고 미확인 분류 표를 펼쳐 86행·가로 넘침 없음·브라우저 오류/경고 없음도 확인했다. 전체 적용 순서 56개 코드/기존 문서 커밋의 전체 SHA, 변경 파일 301개, 파일별 전후 정의 수, 779개 호출 경로, native 분류 근거/파일 해시, 검증/리스크/롤백을 담았다. 최종 인계 문서 커밋은 검증 코드 SHA와 구분한다.
- 전체 카드 분석 진척은 기본 checkout의 고정 기준 `usable-card-analysis-v1.13` 장부 78/100(기록값)을 참고로 표시했으며 이 리팩토링에서 재산정·수정하지 않았다. 모델 학습·사진 추론·실제 provider 요청은 없고 모델 성능 변화는 평가하지 않았다. 다음 모델 개발은 시작하지 않았다.
- 리스크/롤백: 감시·workflow·요청 worker 수명과 결과 불명 복구가 바뀌었다. 실행 직전 철회·세대 변경·중복·재시작·stop·한도·push HEAD/범위를 fake CLI·임시 bare 원격으로 검증했다. 실제 CLI 배포/인증 환경은 미검증이다. 단계와 의존 커밋을 역순으로 `./develop -- git revert <전체 SHA>`하고 dispatching/unknown 장부는 임의 삭제·재실행하지 않는다. 이번 작업의 운영 상태 변경은 없다.

### main 통합 확인 (2026-11-06)
- 후속 계약 pair-control-integration-20261106의 사용자 지정 절차로 main에 채택했다. 통합 전3c2e0b1882e117fc558073b23a9f543e50ec40fe → 검증·첫 원격353319440d3e17d441b51a64970d9e3c7c3b66ea. main 회귀240/239통과/0실패/1기존건너뜀, typecheck·구조검사 통과. .claude/launch.json 해시 불변. 상세 근거·정리·롤백은 후속 계약과 reports/pair-control-main-adoption-20261106.html. 이전 절의 main 미통합은 당시 기록이다.
