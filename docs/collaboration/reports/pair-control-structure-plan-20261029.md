# pair-control 구조 기준 조정안 검토와 적용 계획 (검토 문서 — 기준·코드 변경 없음)

- 작성: Claude, 2026-10-29. 대상 브랜치 `claude/pair-control`, 검토 HEAD `78d030b67db433942bc26e4c855767f80b392225`(현재 HEAD와 같음, 후속 변경 없음), 코드 SHA `0b3341cd8b7a5d3722af94790f79c2f8d0e000f7`, base `be4ce92a0fbb09817e33c322db80ce5bf72abfd3`.
- 이 문서는 **조정안 검토와 계획**이다. PAIR_CODING.md·AGENTS.md·제품 코드·운영 장부는 수정하지 않았고, 구조 기준을 통과했다는 보고가 아니다. 측정은 임시 복사본(`git archive 78d030b`)의 측정 스크립트로 했으며 저장소의 스크립트·코드는 그대로다. 실제 모델 호출·main 통합·운영 push 없음.
- 근거: Codex 재검증 REPORT.md·STRUCTURE_PROPOSAL.md·structure-entry/all.log(기본 checkout, 읽기 전용), 기본 checkout의 현재 PAIR_CODING.md §2.1.

## 0. 결론 먼저

1. **제안된 5개 조정안만으로는 부족하다.** 경계를 지정한 기존 API 목록(제안 3)대로 "말단" 처리해도, 새 관제 코드끼리의 경로가 **최대 8회**(`onMainEnd→…→dispatch→…`), 감시 루프(`tick`)부터 보면 12회로 남는다. 감시 루프→관제 코드 방향(Executor가 `onMainEnd`·`pipelineTick`을 부르는 지점)도 경계로 정의해야 한다.
2. 부족분은 **작은 수정(소스 7곳, 함수 정의 순증 0)** 으로 해결 가능하다고 예상한다(§4, 예상·미검증). Executor 전면 재작성(1200줄·함수 126개)은 필요하지 않다. 단 Executor **내부**의 5회 초과(`cancelAll`·`handoffToMain` 등)는 예외 목록으로 별도 관리해야 하며 이 계획이 줄이지 않는다.
3. 정정: 이전 보고에서 `pushNow`를 4회로 적은 것은 **측정 도구 한계 때문에 틀렸다**. 도구가 `push`라는 이름을 배열 메서드로 보고 `ops.push(...)`를, 매개변수로 넘긴 콜백도 따라가지 않았다. 올바른 값은 **7회**이고 `onMainEnd`는 12회다(§2).
4. 권고: 조정안 승인 시 **§5의 규칙 문구(제안 5개 + 필수 보강 R1~R3)** 로 승인받고, 승인 뒤 §4의 최소 수정과 재측정을 거쳐야 통합 가능하다. 기준 변경 승인만으로 통합이 완료되지 않는다.

## 1. 측정 방법과 한계 (먼저 밝혀 둔다)

- 방법: 임시 복사본의 `structure-trace.mjs`를 확장해(저장소 스크립트 수정 아님) 이름 일치 노이즈 제거·import 해석·`--boundary`(경계 도달 시 그 전이까지만 계산)·`--edge`(정적으로 못 찾는 연결을 가중치로 수동 추가)를 썼다. 전이는 프로젝트 함수 호출 횟수이며 파일·객체 경계를 넘어 센다.
- **도구 한계 (결과 해석에 반영)**
  1. 표준 메서드 이름 제외 목록에 `push`·`add`·`set`·`get`·`delete`·`on`·`write`·`end`가 있어 `ops.push`·`ops.*` 같은 프로젝트 메서드를 누락했다 → 이번 측정에서 객체가 `ops`/`ex`/`this`/`mainOps`일 때는 제외하지 않도록 고쳐 재측정했다.
  2. 매개변수로 받은 콜백 호출(`runPush`의 `verify(plan)`, `pushNow`의 `push(sha, cb)`)은 정적으로 따라가지 못한다 → `pushNow→runPush`(클로저+`runPush` 2회), `runPush→verifyPushScope`(콜백+함수 2회)를 **수동 추가**했다. 실제 연결부: `mainDispatch.ts:pushNow`의 `push(sha, (plan) => verifyPushScope(...))`, `runtime.ts` 관제 연결부의 `push` 클로저, `push.ts:runPush`의 `await verify?.(plan)`.
  3. Mastra 워크플로 재개(`runtime.ts:resumeStep → run.resume`)는 프레임워크 동적 호출이라 정적으로 확정할 수 없다(**미확정**). `resumeStep → executor.ts:resume`로 잡힌 경로는 이름 일치 오탐이다(`Executor.resume`은 프로세스 종료 처리용 비공개 메서드). `integrate_task`는 `runtime.integrate → resumeStep → (Mastra) → workflow.ts integrate-gate → ex.integrate`로 이어지며, 최소 `dispatch`에서 5회 이상(미확정).
  4. getter(`ex.state`·`ex.runtime`·`ex.mainAgent`)는 함수로 세지 않았다.
  5. 표의 `동적(DYN)` 표시는 이름 일치 후보를 포함한 값이다. 이 문서의 최장 경로는 위 항목들을 실제 호출 코드와 대조해 확인한 것이지 전체 경로의 엄밀한 최장 증명은 아니다.
- 저장소의 `structure-trace.mjs`에는 위 한계 수정이 아직 반영되지 않았다(코드 변경이므로 승인 뒤 계획 §4-0에서 반영).

## 2. 경로별 전체 깊이: 현재 vs 제안 경계 적용 후 (A)

경계 변형 3가지를 구분해 계산했다. 변형이 클수록 더 많은 API를 말단으로 본다.
- **현재**: 경계 없음(전체 경로, §1의 도구 보정 포함).
- **제안 3 그대로**: Executor.approve/integrate/runChecks/launchMainProcess/cancelAll, mainRole.swapBlockers, prepare.suggestTaskId, push.preflight/runPush, git·저장 IO 도우미(`git.ts` 공개 함수, `store.save/appendEvent/writeJsonAtomic`, `Executor.audit`)를 말단으로 본다. (`runtime.ts` 연결부 클로저와 `resumeStep`은 목록에 없음.)
- **보강 경계(E2)**: 위 + 새 관제 코드가 실제로 부르는 나머지 Executor API(`limitFor`·`turnOf`·`handoffToMain`·`confirmHandoff`), 연결부 인터페이스 `MainOps` 5개(`runtime.ts`의 approve/integrate/assign/confirm/push)와 `resumeStep`, `locks.acquire/holder/release`.

| 시작 함수 | 현재 | 제안 3 그대로 | 보강 경계(E2) | 해결 여부 |
|---|---:|---:|---:|---|
| `executor.ts:tick`(감시 루프) | 14 | 13 | 12 | ✗ Executor 내부 + 관제 진입 |
| `executor.ts:onAuxEnd` | 13 | 10 | 9 | ✗ |
| `mainEnd.ts:onMainEnd` | 12 | 9 | 8 | ✗ 새 코드끼리 |
| `mainAck.ts:ackSession` | 11 | 8 | 7 | ✗ 새 코드끼리 |
| `pipelineEnd.ts:onTurnEnd` | 11 | 8 | 7 | ✗ 새 코드끼리 |
| `mainActions.ts:applyActions` | 10 | 7 | 6 | ✗ 새 코드끼리 |
| `mainActions.ts:runOne` | 9 | 6 | 5 | ✗ 새 코드끼리 |
| `mainDispatch.ts:dispatch` | 8 | 5 | ≤4 | 보강 경계에서만 ✓ |
| `mainDispatch.ts:pushNow` | **7**(정정) | ≤4 | ≤4 | ✓(경계 뒤 `verifyPushScope`는 별도 진입 3회) |
| `pipelineTick.ts:pipelineTick` | 8 | 7 | 5 | ✗ 새 코드끼리 |
| `pipelineTurn.ts:handleLimit` | 7 | 5 | ≤4 | 보강 경계에서만 ✓ |
| `mainHandover.ts:handoverMain` | 6 | ≤4 | ≤4 | ✓ |
| `pipelineSteps.ts:autoSteps` | 6 | 6 | ≤4 | 보강 경계에서만 ✓(`handoffToMain` 필요) |
| `pipelineTurn.ts:launchTurn` | 5 | ≤4 | ≤4 | ✓ |
| `limitScope.ts:onLimitHit` | 7 | ≤4 | ≤4 | ✓ |
| `runtime.ts:snapshot` | 6 | 6 | 6 | ✗ 새 코드끼리(`pipelineView…whyClosed→matches`) |

### 조정안으로 **해결되는 것**
- 공급자 한도·교대·턴 시작·검사 시작 경로(`onLimitHit`, `handoverMain`, `launchTurn`, `autoSteps`, `pushNow`).
- Executor·push·Git·저장 호출 뒤의 깊이(예: `approve→setStatus→save→writeJsonAtomic`, `commitsBetween→run`)는 말단으로 접힌다.

### 조정안으로 **해결되지 않는 것** ("기존 API를 말단으로 보면 모두 통과"가 아니다)
1. **행동 수행 사슬(새 코드끼리)**: `onMainEnd→onTurnEnd→applyActions→runOne→dispatch→(MainOps/ops.*)` = 경계 직전까지만 5회(마지막 호출을 경계로 보면 5, 호출 대상까지 세면 위 표의 값). `takeover` 경로 `onMainEnd→ackSession→applyActions→runOne→dispatch→ops`도 5회. 경계를 아무리 넓혀도 새 코드 5단 사슬이 남는다.
2. **승인 범위 사슬**: `pipelineTick→scanEvents→revive→turnHold→whyClosed→matches` 5회, `runtime.snapshot→mainRuntimeView→pipelineView→heldRows→prepHolds→whyClosed→matches` 6회.
3. **한도 사슬**: `pipelineTick→handleLimit→handoverMain→saveCheckpoint→buildCheckpoint→(turnOf|revParse)` 5회(`turnOf`를 경계로 본 경우).
4. **감시 루프→관제 진입**: `tick→tickOnce→finalize→onAuxEnd→onMainEnd` 4회가 Executor 쪽에서 이미 소모된다. 제안 3은 "관제→기존 API" 방향만 정의했고 "Executor→관제 진입점" 방향이 없어 `tick`·`onAuxEnd`가 9~14회로 남는다 → **R2 보강 필요**.
5. **Executor 내부 시작점**(예외 목록으로 별도 측정, 이 계획이 줄이지 않음): `cancelAll→cancel→cancelManual→setStatus→event→appendEvent` 5, `handoffToMain→startReviewJob→realReadiness→chargeRisks→scanClaudeSettings→claudeSettingsFiles` 5, `taskControl.createVenv→recheckEnv→preflightChecks→chargeRisks→…` 5.
6. **미확정**: Mastra 재개 경로(§1-3).

## 3. 예외 범위 정확히 고정 (B)

### 3-1. 계속 7개/4회를 적용할 신규·책임 재설계 범위
`tools/pair-control/src/` 중 이 브랜치(base `be4ce92` 이후)에서 새로 만들었거나 책임을 재설계한 파일 — 현재 모두 정의 ≤7(`structure-entry.log`·이번 측정과 일치):
`limitScope`·`approvalGate`·`approvalScope`·`actionPlan`·`pipelineEnd`·`pushOwnership`·`mainAck`·`checkpointBuild`(src/executor), `mainApprovals`·`mainActions`·`mainCheckpoint`·`mainHandover`·`mainDispatch`·`mainEnd`·`mainSerial`·`mainTakeover`·`mainGuard`·`mainOutcome`·`mainTypes`·`pipelineEvents`·`pipelineSteps`·`pipelineTick`·`pipelineTurn`·`pipelineView`·`pipelineState`·`turnBundle`, `ui/js/view-pipeline.js`. 이후 이 파일들이나 새 관제 파일을 추가·수정할 때 **정의 ≤7, 관제 영역 호출 전이 ≤4**를 그대로 적용한다. 새 관제 파일은 예외 목록에 추가할 수 없다.

### 3-2. 함수 수를 동결하는 한정 예외 파일 (현재 HEAD 값, 정의 수 순증 금지)
| 파일 | 현재 | 파일 | 현재 |
|---|---:|---|---:|
| `src/executor/executor.ts` | 126 | `src/executor/mainRole.ts` | 10 |
| `src/runtime.ts` | 32 | `src/executor/contractFile.ts` | 10 |
| `src/executor/push.ts` | 24 | `src/mastra/index.ts` | 60 |
| `src/executor/contract.ts` | 22 | `src/workflow.ts` | 11 |
| `src/executor/prepare.ts` | 20 | `src/ui/js/view-list.js` | 25 |
| `src/executor/git.ts` | 19 | `src/ui/js/logview.js` | 22 |
| `src/executor/taskControl.ts` | 14 | `src/ui/js/form.js` | 20 |
| `src/executor/logstream.ts` | 13 | `src/ui/js/actions.js` | 17 |
| `src/executor/nocharge.ts` | 12 | `src/ui/js/contract-request.js` | 16 |
| `src/executor/adapters.ts` | 11 | `src/ui/js/stages.js` | 14 |
| `src/executor/freeGuard.ts` | 11 | `src/ui/js/panels-work.js`·`panels-release.js` | 각 14 |
| `src/executor/startPrompt.ts` | 11 | `src/ui/js/events.js`·`view-task.js` | 각 13 |
| | | `src/ui/js/app.js` | 11 |
| | | `src/ui/js/form-specs.js` | 8 |

(`executor/` 아래는 Codex `structure-all.log`와 일치, `mastra/`·`ui/js/`는 같은 방법으로 이번에 측정. 실행 파일 `supervisor.mjs`·`paidSignals.mjs`는 별도 확인하지 않았다 — 승인 전에 측정해 목록에 포함 여부를 확정해야 한다.)
이 파일들이 기존 main에 채택됐다는 뜻이 아니라, **tools/pair-control 최초 통합(선행 61 + 이후 커밋)에 대한 명시적 한정 예외**다. `be4ce92` 이후 이 파일들에서 정의 수가 늘지 않았음을 확인했다(executor 126·runtime 32·push 24·git 19·view-list 25 동일).
- **허용 최소 수정 범위**: 연결부 호출·import·전달 인자 변경과 한 줄 라우팅(§4)처럼 **새 함수 정의·새 책임 없이** 신규 코드를 잇는 수정만. 정의 순증·책임 추가는 별도 검토.

### 3-3. 말단(경계)으로 취급할 공개 API의 정확한 목록
**관제 → 기존 코드 방향 (호출 지점까지 세고 내부는 별도 측정):**
- `Executor`: `audit`, `limitFor`, `turnOf`, `launchMainProcess`, `cancelAll`, `runChecks`, `handoffToMain`, `approve`, `integrate`, `confirmHandoff` (새 관제 코드의 실제 호출 지점 `grep ex\.` 결과와 일치하는 10개, 이 외 임의 추가 금지)
- 연결부 인터페이스 `MainOps` 5개(`runtime.ts`: `approve`·`integrate`·`assign`·`confirm`·`push`)와 프레임워크 호출 `resumeStep`(내부는 **미확정**으로 표시)
- `push.ts`: `preflight`, `runPush`
- `mainRole.ts`: `swapBlockers`; `prepare.ts`: `suggestTaskId`
- `git.ts` 공개 함수 전부, `store.ts`: `save`·`appendEvent`·`writeJsonAtomic`, `locks.ts`: `acquire`·`holder`·`release`

**기존 코드 → 관제 진입점 방향 (R2, 신규 필요):** 관제 영역의 측정 시작점으로 삼는 진입점은 `onMainEnd`(Executor 종료 처리가 호출), `pipelineTick`(감시 틱이 호출), `onLimitHit`(가드 콜백이 호출), `handoverMain`·`grantApproval`·`revokeApproval`·`runtime.snapshot`(API 핸들러가 호출), `verifyPushScope`(`runPush`가 훅으로 호출). 이 목록 밖 함수를 진입점으로 선언하지 않는다. `tick→tickOnce→finalize→onAuxEnd`는 Executor 내부(예외 목록 파일)이므로 관제 진입점 앞까지는 Executor 쪽 별도 측정이다.

### 3-4. 확대 금지
다른 프로젝트·모델·데이터·실험 코드(`card_condition/` 등)에는 적용하지 않는다. 예외 목록은 `tools/pair-control` 최초 통합 1회분이며, Executor 분리 계약이 승인·완료되면 폐기를 재검토한다.

## 4. 남는 초과 경로의 최소 수정 계획 (C, 코드 수정은 하지 않았다 — 예상값은 미검증)

모든 수정은 책임을 합치지 않고, 함수 수를 맞추려고 분할·콜백 인라인·비동기 연결을 쓰지 않는다. "호출 전이"는 보강 경계 기준이다.

| # | 변경 | 파일 | 책임·호출 흐름 변화 | 예상 효과 |
|---|---|---|---|---|
| 0 | 측정 도구 수정(표준 메서드 오제외 해결, 콜백 연결, `--boundary/--edge`) | `scripts/structure-trace.mjs` | 측정 정확도만. 제품 동작 무관 | 이 문서의 값을 저장소에서 재현 |
| 1 | 종료 처리 라우팅을 Executor 쪽에서 분기: 파이프라인 턴이면 `onTurnEnd`, 인수 요청이면 `onMainEnd` | `executor.ts`(`onAuxEnd` 분기 1~2줄, 정의 수 불변), `mainEnd.ts`(턴 분기 제거) | 종료 라우팅은 종료를 아는 쪽의 일. `onMainEnd`는 인수 전용 | `onTurnEnd`부터 `applyActions→runOne→dispatch→ops` = 4 |
| 2 | 인수 경로 평탄화: `ackSession`을 `takeOver`(상태 전환)·`finishSession`(마무리)로 나누고 `onMainEnd`가 `applyActions`를 직접 호출 | `mainAck.ts`, `mainEnd.ts` | 같은 단계들을 호출자가 순서대로 부름(합치지 않음) | `onMainEnd→applyActions→runOne→dispatch→ops` = 4 |
| 3 | 증거 검사(`confirmGate`)를 `dispatch`가 아니라 `runOne`의 사전 게이트로 이동, `pushNow` 제거(`dispatch`가 `ops.push(sha, verify)` 직접 호출) | `mainDispatch.ts`, `mainActions.ts` | 실행 전 검증과 실행을 분리(검증은 사전 단계). 동작·검사 순서 동일 | `runOne→confirmGate→git`=3, `dispatch→ops.push`=4 이하 |
| 4 | `handleLimit` 제거: 호출 2곳이 `handoverMain`을 직접 호출하고 "양쪽 한도 보류" 마무리는 짧은 헬퍼 1개로 | `pipelineTurn.ts`, `pipelineEnd.ts`, `pipelineTick.ts` | 한도 교대 호출 지점이 호출자에게 드러남 | `pipelineTick→handoverMain→saveCheckpoint→buildCheckpoint→git` = 4 |
| 5 | `whyClosed` 안에서 `matches` 호출 제거(판정식 한 줄을 인라인), `pipelineView`의 `heldRows` 인라인 | `approvalScope.ts`, `pipelineView.ts`, (`approvalGate.ts`는 기존 `matches` 유지) | **판정식 중복 1곳이 생긴다**(드리프트 위험) → 두 판정이 같은 결과를 내는 표 기반 동등성 테스트로 고정 | `pipelineTick→scanEvents→revive→turnHold→whyClosed` = 4, `snapshot→mainRuntimeView→pipelineView→prepHolds→whyClosed` = 4 |
| 6 | 구조 회귀 테스트를 "경계 지정 측정으로 관제 영역 ≤4"로 확장 | `test/review-fixes.test.ts`(또는 신규 구조 테스트) | 재발 방지 | 규칙 위반을 CI에서 확인 |

- **예상 사이드이펙트/위험**: #1·#2·#3은 행동 수행·인수·턴 종료의 핵심 경로를 건드리므로 선행 안전성 회귀(`main-safety` 12개)·`pipeline` 16개·`review-fixes` 전부를 다시 통과해야 한다. #3은 "검증 실패 시 ID가 처리됨으로 기록돼 재사용되지 않는다"는 기존 동작을 바꾸면 안 된다. #5는 판정 중복 위험을 테스트로만 막는다(원하지 않으면 #5 대신 `approvalGate`에 판정을 두고 호출 1단계를 더 쓰는 대안 → 해당 경로 5회로 남아 예외 목록 필요).
- **검증 방법**: typecheck, 전체 테스트(잠자기 방지 상태에서 `caffeinate -dimsu`), 구조 측정 재실행(보강 경계로 관제 영역 전 진입점 ≤4, Executor 내부는 예외 목록 값과 일치), `pushNow` 등 수동 추가 연결의 재확인, 화면 렌더(내장 브라우저) 재확인.
- **변경량 비교**: 위 6건은 소스 약 7개 파일의 호출 흐름 수정이며 함수 정의 순증 0이 목표다(`runOne`/`dispatch`/`ackSession` 책임 재배치 포함). **대안 — Executor 전면 재설계**로 문자 그대로 모든 시작 함수 ≤4를 달성하려면: `executor.ts`(1200줄, 정의 126)를 승인·통합·검사·실행·한도·감시 모듈로 쪼개고 각 공개 메서드를 내부 1~2회로 재작성해야 한다. `tick→…→onAuxEnd` 같은 감시 사슬이 이미 4단이라 관제 코드까지 문자 그대로 4회를 맞추려면 이벤트 큐 같은 **구조 변경**이 필요한데, 이는 "비동기 연결로 깊이 감추기" 금지와 충돌할 수 있다. 별도 대형 계약이 필요하고 회귀 범위도 전체 테스트 174개에 걸친다. 이번 통합에는 비례하지 않는다고 판단한다.
- 이 계획으로도 **Executor 내부 5회 경로(§2-5)와 미확정 Mastra 재개 경로는 남는다.** 예외 목록의 "별도 측정" 항목으로 공개하며 통과로 표시하지 않는다.

## 5. 사용자 승인용 문구 (D) — PAIR_CODING.md 제안 diff (적용 안 함)

`PAIR_CODING.md` §2.1의 마지막 불릿 뒤에 다음을 추가한다(기존 문장은 수정하지 않는다).

```diff
+- **한정 예외 — `tools/pair-control` 최초 통합 (2026-10-29 사용자 승인 시 유효, 이 항목만의 예외)**
+  1. 범위: `tools/pair-control`의 `be4ce92`(선행 61 커밋 이후 기준 base)부터 검토 코드 `0b3341c`까지 미통합 구현의 최초 통합 1회. 다른 프로젝트·모델·데이터·실험 코드에는 적용하지 않는다.
+  2. 신규·책임 재설계 파일(작업 문서 `pair-control-structure-plan-20261029`의 3-1 목록)은 익명 콜백 포함 함수 정의 ≤7과 관제 영역 호출 전이 ≤4를 그대로 지킨다. 새 관제 파일은 예외 목록에 넣지 않는다.
+  3. 선행 구현의 대형 파일(같은 문서 3-2 목록)은 파일별 현재 함수 수를 **동결**한다. 정의 수 순증·새 책임 추가는 금지하고, 신규 코드를 잇는 호출·import·분기 수정만 허용한다. 이 목록은 main에 채택된 기준 충족이 아니라 이번 최초 통합의 한정 예외다.
+  4. 호출 전이는 경계 목록(같은 문서 3-3)의 공개 API 호출 지점까지 세고, 경계 안쪽은 별도로 측정·검토한다. 경계는 관제→기존 코드와 기존 코드→관제 진입점 양방향으로 정의하며, 목록 밖 함수를 임의로 말단·진입점으로 선언하지 않는다. 프레임워크 동적 호출은 미확정으로 표시한다.
+  5. 전체 실제 경로(경계 안쪽 포함)의 깊이와 안전성 검토·회귀는 계속 공개·수행한다. 예: 행동 수행 경로의 전체 값을 4회로 바꿔 적지 않는다.
+  6. 경계 기준을 적용해도 새 관제 코드끼리 4회를 넘는 경로가 남으면 이 예외로 덮지 않고 수정한 뒤 재측정한다.
+  7. 이 예외의 승인만으로 통합이 완료되지 않는다. 통합 전 최신 main·계약·선행 커밋 대응, 통합 소스의 타입 검사·전체 테스트, 구조 재측정이 필요하다. 사람 라벨·평가·실험 승인, 모델 호출 제한, 운영 승인 장부, 일반 push·force 금지 규칙은 그대로 유지한다.
+  8. Executor 분리 계약이 승인·완료되면 이 예외의 폐기를 재검토한다.
```

보강 R1~R3(제안 5개 대비 추가): **R1** 경계는 "새 관제 코드가 실제 호출하는 API"만(위 목록)으로 닫는다. **R2** 기존 코드→관제 진입점 방향도 경계로 정의한다. **R3** 매개변수 콜백·프레임워크 동적 호출은 정적 도구가 못 따라가므로 측정 시 수동 연결을 기록하고 미확정으로 표시한다.

## 6. 리스크·롤백·사용자 결정

- **리스크**: (1) 예외가 선례가 될 수 있음 → 범위·폐기 조건·동결 목록을 규칙에 명시. (2) §4 수정이 핵심 경로를 건드림 → 회귀·재측정 필수. (3) 판정식 중복(#5). (4) 도구 한계로 측정이 낮게 나올 수 있음(이번에 `pushNow` 정정) → 수동 연결 기록 유지, 코드 리뷰어가 실제 호출자 대조.
- **롤백**: 이 문서는 문서 커밋 1개이며 `git revert <문서 커밋>`으로 제거. 규칙을 승인하지 않으면 PAIR_CODING.md는 그대로이고 통합은 계속 보류(대안: Executor 분리 계약을 새로 만들어 문자 그대로 충족).
- **사용자가 결정할 사항**
  1. 한정 예외(§5 규칙)와 보강 R1~R3 승인 여부, 또는 Executor 전면 재설계(별도 대형 계약) 선택.
  2. 승인 시 §3-2 동결 목록(특히 `supervisor.mjs`·`paidSignals.mjs` 측정 결과 반영)과 §3-3 경계 목록 확정.
  3. §4 수정에서 #5의 판정식 중복을 허용할지(허용 / 비허용 후 해당 경로 예외).
  4. 승인 후 §4를 이 브랜치에서 진행할지(허용 파일: executor.ts 분기 1~2줄, runtime.ts·push.ts 무변경 예정, mainEnd/mainAck/mainDispatch/mainActions/pipeline*/approvalScope/pipelineView, 측정 스크립트, 구조 테스트).

## 7. 실행 기록

- 확인: 작업 트리 변경 없음, HEAD `78d030b` 유지. 읽은 문서: Codex REPORT.md·STRUCTURE_PROPOSAL.md·structure-entry/all.log, 기본 checkout PAIR_CODING.md §2.1, 이 브랜치 계약·보고서.
- 실행: 임시 복사본에서 측정 스크립트 확장판으로 `--all`(경계 없음/제안 3/보강 E2), `tick·tickOnce·finalize·onAuxEnd`·`pushNow` 등 단독 시작 측정, 함수 수(executor·mastra·workflow·ui 전체) 측정. 모델 호출·테스트 실행·코드 수정·통합·push 없음.
- 미실행: §4 수정, 예상 깊이의 실제 재측정, 테스트 재실행, `supervisor.mjs`·`paidSignals.mjs` 측정.
- 진척: 전체 개발 진척 35/100(`usable-card-analysis-v1.0`), 이번 +0. 문서 작성은 코드 개선 완료나 구조 기준 통과가 아니다.
