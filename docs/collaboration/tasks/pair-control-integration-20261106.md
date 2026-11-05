# pair-control 후속 통합·복구 검증

- task_id: pair-control-integration-20261106
- owner: Codex
- status: implementing
- base_sha: c4179271756645882b917c417ac96f97578fa355
- integration_base_sha: 3c2e0b1882e117fc558073b23a9f543e50ec40fe (fetch 확인 main=origin/main)
- branch: codex/pair-control-integration-20261106
- goal: 최신 main과 도구 전체를 별도 브랜치에서 결합·검증하고 실행 직전 stop/승인 철회 반례를 보완한다.
- allowed_files: 이 계약, docs/collaboration/reports/pair-control-integration-20261106.html, tools/pair-control/src/executor/taskLaunch.ts, tools/pair-control/src/executor/taskSpawn.ts, tools/pair-control/src/executor/taskReserve.ts, tools/pair-control/src/runtimeRequests.ts, tools/pair-control/src/runtimeRequestPolicy.ts, tools/pair-control/test/launch-authority.test.ts. 최신 main 병합 유입 파일은 기존 커밋 그대로 보존하고 AGENTS.md/PAIR_CODING.md/README.md 충돌만 양쪽 지침·도구 안내를 대조해 해결한다.
- forbidden_files: 모델·worker·라벨·평가 자료 수동 변경, 비밀 설정, 다른 checkout 미커밋 파일. 실제 모델 호출·실제 CLI 모델 요청·학습·사진 추론·운영 push 금지. fake CLI·합성 fixture·임시 bare 원격만 사용.
- contract: approvalGate 단일 승인 판정, 세션·세대·stop·한도·결과 불명·재시작·push 범위 보호 유지. 기본 checkout 미추적 .claude/는 건드리지 않고 깨끗해지기 전 main 통합 보류.
- structure: 변경 전 270파일/779정의, 최대 정의7/전이4. 변경 파일별 전후 정의·경로를 기록. main 원본 도메인 파일은 구조 리팩토링 범위 밖.
- checks: SHA/충돌 확인, typecheck, structure-trace --check, 실행 전 상태 변경 회귀, 전체 npm test, diff --check, HTML 생성·내용 대조·실제 렌더 확인.
- experiment: 없음, 모델 성능 미평가.
- rollback: 기존 완료 SHA 보존. 후속 변경은 의존 역순 git revert, dispatching/unknown 장부 삭제·자동 재실행 금지.

## 초기 확인
- 기존 작업 트리 깨끗함, origin/main fetch 완료.
- 기본 checkout 미추적 .claude/로 main 통합 보류. stash/reset/타 작업 정리 금지.
- 원시 미확인86개는 기존 코드 SHA에서 감사했으며 도구 출력0으로 바꾸지 않는다.
- 최초 계약 작성 명령은 python 경로 부재로 실패했다. 계약 고정 전 진행한 병합은 즉시 abort했고 원상 복구를 확인했다. /usr/bin/python3로 수정해 재개한다.
