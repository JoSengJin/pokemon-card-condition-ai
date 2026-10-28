# 작업 계약: pair-control 교대 후 연속 페어코딩 연결(검토 P1-6)

- task_id: `pair-control-main-pipeline-20261029`
- owner: Claude (구현)
- status: implementing
- base_sha: `01f36e0667aecaf98d5cba3bec1f09059a9deb09` (선행 `pair-control-main-safety-20261029` 인계 SHA — 검증·커밋 완료 확인, 이 worktree 미커밋 변경 없음)
- branch: `claude/pair-control` (기존 worktree 재사용)
- 통합·push·실제 모델 호출: 하지 않음. 합성 push는 임시 bare 원격에만 한다. main 통합과 실제 push는 현재 메인의 최종 검토에 남긴다.
- 근거: 통합 검토 REPORT.md "교대 후 페어코딩 연결 누락"(기본 checkout `artifacts/pair-control-main-rotation-review-20261029/`, 읽기 전용), 선행 계약·보고서, 기본 checkout의 현재 `AGENTS.md`·`PAIR_CODING.md`(읽기 전용, 이 브랜치 사본은 낡아 수정 금지).

## 목표

교대 후 새 메인이 한 번 응답하고 끝나지 않고, 구현 결과 도착 같은 의미 있는 상태 변화마다 승인 범위 안에서 다음 단계를 이어 처리한다. 새 승인·권한을 만들지 않는다.

## 완료 조건

1. 인수: 새 메인 요청문과 체크포인트에 목표·승인 범위·계약·SHA·소유 파일·검사 근거·미해결 판단이 들어가며, 이전 대화 기억 승계를 가정하지 않는다.
2. 배정+시작: `assign_task`는 승인된 ID로 준비한 뒤 기존 시작 경로(`startTask`)로 구현을 시작한다(`input.start:false`면 준비만). 시작이 막히면 행동은 실패로 기록한다.
3. 결과 수집 후: 승인 범위에 덮인 작업은 도구가 지정 검사(`runChecks`)와 인계 문서 생성(`handoffToMain`)을 단계당 한 번만 수행한다(모델 호출 없음). 실패·미실행·결과 불명은 통과가 아니며 해당 작업 단계에서 멈춘다.
4. 의미 검토 증거: 신규 `confirm_handoff` 행동은 현재 결과 SHA, 변경 파일 목록 전체, 도구가 계산한 diff 해시, 비어 있지 않은 검토 메모가 모두 일치해야 하고, 구현 에이전트와 같은 에이전트의 확인은 독립 확인이 아니므로 거부한다.
5. 통합: `approve_task`→`integrate_task`는 기존 실제 상태 확인(통합·HEAD·통합 후 검사)을 통과해야 하며, 같은 응답 안에서 한 작업의 앞 행동이 실패하면 뒤 행동을 수행하지 않는다.
6. push: 신규 `push_main`은 승인 장부에 해당 행동이 있어야 하고, 점검 막힘 없음·계획의 모든 작업이 `integrate_task` 승인 범위·확인 SHA 일치일 때만 기존 `preflight`/`runPush`(일반 push, force 없음)로 수행한다. push 결과 불명은 재시도하지 않는다.
7. 이벤트: 감시 틱이 상태를 읽어 이벤트(`result_ready`·`approved`·`integrated`)를 저장 장부에 한 번만 등록하고, 이벤트 묶음마다 현재 메인에게 턴 한 번을 준다(같은 이벤트·같은 세대에 두 번째 턴 없음). 모델 응답은 제안이며 실행 직전 기존 도구 검사(세션·세대·승인·대상·현재 상태)를 통과해야 한다. 상시 재토론·무한 폴링 없음.
8. 진행 중 구현 인수: 교대는 구현 에이전트를 중단하지 않고, 교대 후 도착한 결과는 현재 메인의 턴으로 처리된다. 수동 프롬프트 복사·재승인 불필요(세션 묶인 승인은 승계하지 않음).
9. 한도·중단: 턴이 한도로 끝나면 그 에이전트를 기록하고 상대 메인으로 기존 한도 교대를 연결하며, 이벤트는 새 세대의 턴에서 한 번 처리한다. 양쪽 한도면 의존 이벤트를 보류하고 체크포인트를 남긴다. 결과 불명 턴·행동은 재시도하지 않는다. 지연·이전 세대 응답은 상태를 바꾸지 못한다.
10. 복구: 서버 재시작 후 진행 중이던 턴·적용 중이던 행동은 저장 상태를 대조해 결과 불명으로 보존하고 중복 실행하지 않는다.
11. 완료 표시: 화면 요약에 "메인 인수 완료"(세션), "개별 행동 성공", "작업 파이프라인 완료(원격 push 검증된 작업만)"를 따로 표시한다.

## 허용 파일

- 신규(src/executor): `pipelineState.ts`, `pipelineEvents.ts`, `pipelineSteps.ts`, `turnBundle.ts`, `pipelineTurn.ts`, `pipelineTick.ts`, `mainDispatch.ts`, `pipelineView.ts`
- 수정: `mainTypes.ts`(자료형·행동 종류), `mainGuard.ts`(새 행동 형식), `mainApprovals.ts`(새 행동 허용 목록), `mainActions.ts`(디스패치 위임·의존 행동 차단), `mainOutcome.ts`(배정 시작 확인), `mainEnd.ts`(턴 종료 분기), `executor.ts`(감시 틱에서 `pipelineTick` 호출 1줄·import 1줄), `src/runtime.ts`(assign+start, 새 ops, 화면 요약), `mainTakeover.ts`(요청문에 목표·행동 종류 보강)
- 테스트: 신규 `test/pipeline.test.ts`, `test/fake-cli/takeover.mjs`·`claude`·`codex`(턴 응답 흉내만), 기존 테스트는 기대 변경이 불가피할 때만
- 문서: 이 계약, `tools/pair-control/README.md`(연속 흐름 한 단락), `docs/collaboration/reports/main-pipeline-20261029.html`
- 금지: `AGENTS.md`/`PAIR_CODING.md`(이 브랜치 사본), 데이터·라벨·모델·운영 코드, 기본 checkout, 운영 `.state`·승인 장부, 실제 Codex/Claude/Gemini 호출, 승인 범위 확대

## 검사 (모두 fake CLI·합성 bare 원격)

- `npm run typecheck`, `test/pipeline.test.ts`, `npm test` 전체(선행 안전성 회귀 포함)
- 시나리오: Codex→Claude·Claude→Codex / 교대 후 도착 결과의 자동 처리 / 준비→구현 시작→수집→검사·검토→통합→통합 후 검사→합성 원격 push / 승인 밖·조건 미충족·검사 실패 차단 / 실행 중 재교대·지연·중복 이벤트·서버 재시작 / 한쪽·양쪽 한도 / 결과 불명 시 중복 요청·실행·push 없음
- 구조: `node scripts/structure-trace.mjs`로 신규 파일 함수 수(≤7)와 호출 전이를 측정해 보고(기준 초과 시 예외 임의 승인 금지)

## 구조 기준(변경 전 → 목표)

mainActions 6→≤7, mainApprovals 5→≤7, mainOutcome 1, mainEnd 1, mainGuard 4, mainTypes 0(자료형만), 신규 파일 각 ≤7. 변경 후 값은 인계에 기록한다. 기존 Executor 내부로 이어지는 호출 경로는 선행 보고와 같은 이유로 4회를 넘으며 채택 보류로 보고한다.

## HTML

`docs/collaboration/reports/main-pipeline-20261029.html` — 생성·내용 대조·열기(요청 성공과 렌더 확인 구분)를 handoff에 기록한다.
