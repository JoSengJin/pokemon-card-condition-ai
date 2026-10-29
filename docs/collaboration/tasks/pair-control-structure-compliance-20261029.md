# 작업 계약: pair-control 구조 기준 준수 (한정 예외·동결 없음)

- task_id: `pair-control-structure-compliance-20261029`
- owner: Claude (구현)
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
(단계 진행 상황과 최종 SHA·측정 전/후는 완료 시 보고서에 기록)
