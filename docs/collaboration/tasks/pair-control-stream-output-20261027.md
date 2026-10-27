# pair-control 스트리밍 출력 모드와 무과금 가드 보강 — Claude 배정

- task_id: `pair-control-stream-output-20261027`
- owner: Claude
- status: handoff (코드 커밋 `df943b9987f328e4cef725250504350d4665af6b`)
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

- 코드 커밋 `df943b9987f328e4cef725250504350d4665af6b` (검사는 같은 작업 트리에서 실행).
- 함수 수: `streamGuard.ts` 2(eventSignal·scanOutput), `events.js` 7(clip·toolLine·resultText·claudeEvent·codexEvent·fmtLine·appendLog), `logview.js` 7, `app.js` 5. `executor.ts`는 `readNewLog` 본문만, `adapters.ts`는 probe/realPlan 조건 추가, `config.ts`는 `streamOutput` 필드 추가.
- 호출 경로(최장 전이 4): `pollLog → appendLog → fmtLine → claudeEvent → toolLine|clip`, `tick → readNewLog → scanOutput → eventSignal`(전이 3). 동적 경로: 이벤트 리스너.
- 동작: `streamOutput`(기본 true)이 켜져 있고 `--help`에서 옵션이 확인된 CLI만 `claude --print --output-format=stream-json --verbose` / `codex exec --json`으로 실행(아니면 텍스트 모드). 가드는 구조화 이벤트에서 신호 필드만 검사하고 내용 이벤트는 건너뛴다. 서비스 종료·알림은 기존 `trip`/`notifyUser`/알림 파일 경로 그대로(`paid_stream` 사유 추가). 화면은 이벤트를 읽기 쉬운 줄로 변환하고 모르는 이벤트·JSON 아닌 줄은 원문, 비용 필드는 숨김.
- checks: typecheck 통과, `npm test` 95/95(기존 85 + 신규 10: stream.test.ts 6, ui-events.test.ts 4(로그 행 모델 변경으로 ui-logview 2개 수정)). 검사 요지: 내용 이벤트가 과금 문구를 담아도 종료 안 함 / `apiKeySource` user·project·org·temporary는 종료·알림 파일, none·oauth·모르는 값은 종료 안 함 / 결제·크레딧 오류 필드·오류 결과·실패한 턴·한도 거절 이벤트 / 텍스트 줄은 기존대로 글 전체 검사 / 잘린 JSON 줄 보류 / mock 스트림 실행이 오탐 없이 검토 대기까지 감 / mock `apiKeySource=user`·오류 이벤트가 서비스 종료 신호를 냄 / 실제 CLI 계획의 옵션이 확인+설정일 때만 붙고 꺼지면 텍스트 모드, 금지 옵션 검사·실제 호출 승인 거부는 그대로 / 이벤트 변환(Claude·Codex 샘플).
- 브라우저(사용자 서버 4111, 읽기 전용 + 페이지 안 가짜 응답, 서버·상태 변경 0, POST 0건): JSONL 이벤트 10줄이 `[시작] 모델 … · 인증 none`, `계약을 …`, `[Read] 파일`, `→ 결과`, `$ 명령`, `[완료] 정상 종료 · 154초 · 6턴`로 변환되어 흐르고 비용·JSON 원문은 보이지 않으며 줄 색·받은 시각 정상.
- **미확인(중요)**: 실제 Claude·Codex 이벤트 형식. 이벤트 모양은 도움말·문서·기억에 근거한 샘플이고 실제 모델 호출은 하지 않았다. 다음 실제 작업에서 ① `--output-format=stream-json --verbose` 조합이 실행되는지 ② 구독 로그인의 `apiKeySource` 값이 `none`인지(다른 값이 API 키 경로 값(user·project·org·temporary)이면 가드가 서비스를 종료하고 알림을 보낸다 — 사용자 판단 필요) ③ 변환 줄이 읽을 만한지 확인해야 한다. 변환하지 못하는 이벤트는 원문으로 보인다. 끄려면 `config.local.json`에 `"streamOutput": false`.
- 알려진 한계: 가드는 구조화 이벤트의 내용(코드·파일 본문)을 보지 않으므로, 과금 안내가 오직 내용 이벤트에만 나오는 경우는 놓친다(그 문구는 `is_error` 결과·`error` 이벤트로도 나오는 것이 정상). 프로브는 서버가 켜질 때와 "CLI 다시 확인"을 누를 때 옵션(`stream`)을 갱신한다.
- 롤백: 코드·문서 커밋 `git revert`, 또는 설정 `streamOutput:false`.
