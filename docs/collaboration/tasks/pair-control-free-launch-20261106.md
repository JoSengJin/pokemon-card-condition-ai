# pair-control 무료 조건 실행 경로 루프 보완

- task_id: pair-control-free-launch-20261106
- owner: Codex
- status: implementing
- base_sha: 07079575faac6b66eddd4be02d594fc737ca1b78
- branch: codex/pair-control-free-launch-20261106
- goal: 구현·리뷰·메인 교대의 실행 직전 무료 조건 누락/대기 중 변경을 fake CLI로 재현하고, 비용 조건 미확인·유료 경로·중단이면 프로세스를 시작하지 않도록 보완한다.
- allowed_files: tools/pair-control/src/executor/taskLaunch.ts, tools/pair-control/src/executor/reviewStart.ts, tools/pair-control/src/executor/executor.ts, tools/pair-control/src/executor/codexSettings.ts, tools/pair-control/test/free-launch.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-free-launch-20261106.html.
- forbidden_files: 운영 config/state/장부, .claude/, 모델·worker·사진·라벨·평가·진척 기준, 다른 worktree 변경/서버 조작. 실제 모델 프롬프트·학습·사진 추론 금지. 금지 해제·추가 크레딧 꺼짐은 추정하지 않는다. fake CLI·임시 저장소만 실행한다.
- contract: 무료 신호 판정은 기존 realReadiness/scanCodexConfig/scanClaudeSettings 재사용. 승인 판정식 approvalGate는 변경하지 않는다. stop·한도·구독/실행 승인 철회·API 환경/설정·실행 cwd를 최종 검사하고 실패/결과 불명은 재실행하지 않는다. 확인되지 않은 profile 선택은 무료로 간주하지 않는다.
- structure: src/scripts 파일당 정의7·실제 호출전이4 유지. 시작270파일/780정의. 전후 변경 파일 정의 수와 경로 기록. 임의 경계/콜백으로 숨기기 금지.
- checks: 수정 전 실패 재현 → 최소 수정 → 관련 회귀/typecheck/structure --check → 전체 회귀. main 통합 때 최신 기준·잠금·.claude 보존·실험/검토 실행 부재 확인, main 관련 회귀·일반 push·원격 SHA 대조. HTML 생성·내용 대조·실제 렌더. 운영 서버 재시작은 하지 않는다.
- experiment: 없음, 모델 성능 평가/진척 재산정 없음.
- rollback: 후속 커밋 역순 git revert, 운영 상태/결과 불명 장부 삭제·자동 재실행 금지.

## 읽기 점검
- 구현은 사전 검사 후 probe/startPrompt 대기가 있으나 마지막에 과금 환경/설정을 다시 보지 않는다. 리뷰는 readiness 뒤 worktreeFingerprint 대기가 있다. 메인 실제 실행 함수는 stop 및 실제 cwd의 Claude 설정을 검사하지 않는다. 각각 실제 시작 경로로 반례를 검증한다.
- Codex 전역 profile 선택은 별도 설정을 적용할 수 있으나 현재 무료 스캔이 해석하지 못한다. 무료 조건 불확실 시 보류한다. 프로젝트 Codex 설정의 과금 키 적용 여부를 추정해 기능을 확대하지 않는다.
- 공식 문서 https://learn.chatgpt.com/docs/config-file/config-basic 와 https://code.claude.com/docs/en/settings 를 열어 설정 scope를 확인했다. 메타데이터/구독 로그인만으로 실제 무료 과금을 증명하지 않는다.
