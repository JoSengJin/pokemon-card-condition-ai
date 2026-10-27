# pair-control 스트리밍 출력 모드와 무과금 가드 보강 — Claude 배정

- task_id: `pair-control-stream-output-20261027`
- owner: Claude
- status: implementing
- base_sha: `6463a48` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 배경

실제 `claude --print`는 마지막 요약만 한 번에 출력해서 실시간 로그 창에 중간 과정이 흐르지 않는다. 사용자가 "무료면 적용하고, 유료 전환 시 알려주고 서비스 중단"으로 승인했다. 두 CLI 모두 줄 단위 이벤트 출력이 있다(`claude --print --output-format stream-json --verbose`, `codex exec --json`; 도움말로 옵션 존재 확인). 추가 요금은 없고 같은 구독 실행이며 무과금 가드 금지 목록(`--bare`, `--max-budget-usd`, `--betas`)에 없다.

## 핵심 위험: 스트리밍이 무과금 가드를 오탐시킬 수 있다

지금 가드는 에이전트 출력 전체를 과금 문구로 검색한다. 텍스트 모드에서는 최종 요약만 나오지만, 스트리밍 이벤트에는 에이전트가 읽은 파일 내용(도구 결과)과 쓴 코드가 그대로 들어간다. 이 저장소의 `paidSignals.mjs`에는 "credit balance" 같은 문구가 있어서, 에이전트가 그 파일을 읽기만 해도 서비스가 종료될 수 있다. 그래서 **구조화된 이벤트는 신호가 되는 필드만 검사**하고 내용 이벤트는 건너뛴다.

## 목표

1. **어댑터**: 설정 `streamOutput`(기본 true)이 켜져 있고 `--help`에서 옵션이 확인되면 Claude는 `--output-format=stream-json --verbose`, Codex는 `exec --json`을 쓴다. 확인되지 않거나 설정이 꺼져 있으면 지금처럼 텍스트 모드. mock에는 `stream` 시나리오 추가.
2. **가드 보강**(서비스 종료·알림은 기존 `trip`/`notifyUser` 경로 그대로):
   - 구조화된 이벤트(`{"type":…}` 한 줄)는 다음만 검사: `system`/`init`의 `apiKeySource`가 API 키 경로(`user`·`project`·`org`·`temporary`)이면 즉시 종료·알림, `error` 필드의 결제·크레딧·쿼터 계열, `is_error`인 `result`와 `error`·`turn.failed` 이벤트의 오류 문구(기존 과금/한도 패턴 적용), 한도 거절 이벤트는 정지(서비스 유지). 내용 이벤트(assistant/user/item.*)는 검사하지 않는다.
   - 줄이 구조화 이벤트가 아니면 지금과 똑같이 글 전체를 검사한다(텍스트 모드·stderr 포함).
   - JSON 줄이 읽는 중간에 잘려 있으면 다음 주기에 이어 읽는다.
3. **화면**: 이벤트를 읽기 쉬운 줄로 바꿔 로그 창에 보여 준다(`$ 명령`, `[도구] 파일`, `→ 결과`, `[완료]`). 모르는 이벤트와 JSON이 아닌 줄은 원문 그대로. 원문 JSON은 로그 파일에 그대로 남는다.

## allowed_files

1. `tools/pair-control/src/executor/streamGuard.ts` (신규), `src/executor/adapters.ts`, `src/executor/config.ts`, `src/executor/contract.ts`(mock 시나리오 이름만), `src/executor/executor.ts`(`readNewLog` 본문만), `mock/mock-agent.mjs`, `config.example.json`
2. `tools/pair-control/src/ui/**` (신규 `js/events.js`, 로그 행 모델 변경)
3. `tools/pair-control/test/stream.test.ts`(신규), `test/ui-events.test.ts`(신규), `test/ui-logview.test.ts`
4. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-stream-output-20261027.html`

## forbidden

위 밖 전부. 기존 과금·한도 패턴 목록, 환경변수·설정 검사(`nocharge.ts`), 시작 거부 규칙은 약화하지 않는다. **실제 Claude·Codex 모델을 호출하지 않는다**(mock과 샘플 이벤트로만 검사). 사용자의 서버·작업을 시작·종료하지 않는다.

## 구조 기준

`streamGuard.ts` 7개 이하, `events.js` 7개 이하, 호출 전이 4회 이하(`pollLog → appendLog → fmtLine → claudeEvent → clip`, `tick → readNewLog → scanOutput → eventSignal`). 실행기는 기존 파일(변경은 한 함수 본문).

## checks

1. `npm run typecheck`, `npm test`(기존 85 + 신규).
2. 신규: 가드 단위(키 경로·내용 이벤트 오탐 없음·결제 오류·한도·텍스트 줄 그대로·잘린 JSON 줄) / mock 스트림 실행이 오탐 없이 끝남 / `apiKeySource=user` 이벤트에서 서비스 종료 신호 / 어댑터 옵션 조건 / 이벤트 변환 샘플.
3. 사용자 서버 읽기 전용 + 페이지 안 가짜 응답으로 변환 결과 확인.
4. 성과·진척 HTML, `git diff --check`, 깨끗한 트리.

## 결과

(인계 시 갱신)
