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
