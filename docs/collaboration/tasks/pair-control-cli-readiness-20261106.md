# pair-control CLI 연결 준비·실패 차단

- task_id: pair-control-cli-readiness-20261106
- owner: Codex
- status: implementing
- base_sha: e9b16d7bcc94829ffa6471189a617ec1a21a1026
- branch: codex/pair-control-cli-readiness-20261106
- goal: 설치된 실제 CLI help 옵션과 어댑터를 대조하고 실패한 help/로그인 점검이 실행 승인으로 이어지지 않도록 회귀로 검증한다.
- allowed_files: tools/pair-control/src/executor/adapterProbe.ts, tools/pair-control/src/executor/adapterPlan.ts, tools/pair-control/src/executor/codexSettings.ts, tools/pair-control/test/adapter-probe.test.ts, tools/pair-control/test/stream.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-cli-readiness-20261106.html.
- forbidden_files: 운영 설정/상태/장부, 모델/worker/라벨/평가/진척 자료, .claude/, 다른 작업 파일. 실제 모델 요청·학습·사진 추론·실제 CLI exec/--print 실행 금지. 실제 CLI는 --version/--help 및 필요한 로그인 상태 읽기만 허용하며 구독·호출 승인 설정은 켜지 않는다. 회귀는 fake CLI·임시 저장소만 사용한다.
- contract: approvalGate 승인 판정은 그대로. 로그인 문자열 판정은 기존 codexLoginIsChatgpt 단일 구현 재사용. help 실패·로그인 상태 실패·미확인은 실행 불가로 보존하며 구독 확인과 실제 호출 승인을 대신하지 않는다.
- structure: 최대 정의7/전이4 유지. 현재 도구270파일/779정의. 변경 파일 전후 정의 수 및 경로를 기록한다.
- checks: 실패 재현 회귀 → 보완 → typecheck/관련 회귀/구조 --check → 전체 npm test → HTML 생성·대조·실제 렌더. main 통합 시 최신 main·.claude 보존·잠금/실행 상태를 재확인하고 관련 검사·일반 push·원격 SHA 확인.
- experiment: 없음, 모델 성능 미평가.
- rollback: 새 커밋 git revert, 작업 결과 불명 장부 삭제/재실행 금지. 운영 설정 변경 없음.

## 설치 메타데이터 확인
- codex-cli0.164.0, Claude Code2.1.310의 --version/--help만 실행. Codex --cd/--sandbox/workspace-write/--json, Claude --print/--permission-mode acceptEdits/--allowedTools/stream-json/--verbose가 help에 존재한다. Codex sandbox의 PATH alias 쓰기 경고는 도움말 명령의 종료0과 구분한다.
- 공식 OpenAI CLI reference https://learn.chatgpt.com/docs/cli/reference 를 열어 비대화형·권한 옵션 계약을 대조했다. 실제 모델 요청 없음.
- 코드 검토에서 probe는 help 종료코드가 실패여도 출력의 옵션을 인정하고 login status 실패 출력도 그대로 신뢰한다. realPlan은 화면 readiness와 달리 Codex 로그인 판정을 재검사하지 않는다. 각각 fake CLI 반례로 먼저 확인한다.

## 보완·관련 검증
- 수정 전 fake CLI 반례5개 모두 실패: 실패 help 출력 신뢰, 실패 login 문구 신뢰, 부정/만료 부분 일치, 실제 실행 계획의 API key/미확인 로그인 허용, 직접 시작 경로의 감독 실행 허용. 실제 모델은 없으며 fake 명령만 실행했다. 로그 pair-cli-readiness-before-20261106.log(세션 /tmp).
- adapterProbe: help 종료0일 때만 옵션 인정. login 종료코드 검사, 알려진 PATH alias 시작 경고 분리, 로그인 성공은 기존 단일 판정으로 정규화하고 실패·미확인 원문은 노출하지 않음.
- codexLoginIsChatgpt: 전체 문장 일치로 부정·만료·추가 설명 부분 일치 거부. realPlan: 이 판정을 실제 작업 시작에도 재사용. streaming 테스트 fixture는 정상 로그인 근거를 명시했다.
- 새 회귀7개+기존 관련33개 총40통과/실패0/건너뜀0, 60072.847417ms. typecheck 통과. 구조 --check 통과, adapterProbe3→4, adapterPlan4→4, codexSettings2→2, 전체270파일/780정의, 최대전이4/초과0/순환0. serviceTick→launch→probe→filter callback 또는 serviceTick→launch→realPlan→codexLoginIsChatgpt 등 경로는 한도 이내다.
- 원시 미확인86개 호출 지점은 기존과 동일. 외부2734개, 설치 라이브러리와 기존 native 분류 근거 대조는 최종 인계에 기록한다.
- 보완 코드를 실제 CLI 메타데이터에 적용: Codex0.164.0의 필수2옵션·stream·ChatGPT login, Claude2.1.310의 필수3옵션·stream 확인. 실제 CLI 실행 인자는 version/help/login status로 제한했고 실제 프롬프트 실행0. 구독 추가 크레딧·잔여 한도·실제 교대는 여전히 미확인.
