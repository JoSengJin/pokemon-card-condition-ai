# 관제 API 상태 변경 직전 권한·세대 재검증

- task_id: pair-control-api-finalization-20261107
- owner: Codex
- status: integrated
- base_sha: 7a3b217845da994a31fd36800eb4813fc6a98c56
- branch: codex/pair-control-api-finalization-20261107
- goal: 배정/승인/인계 확인/통합/메인 표시 이양이 준비 await 뒤 오래된 권한·세대로 상태나 Git을 바꾸지 않도록 검증한다.
- allowed_files: tools/pair-control/src/executor/approvalGate.ts, tools/pair-control/src/runtimeRequestPolicy.ts, tools/pair-control/src/executor/executorPolicy.ts, tools/pair-control/src/executor/verificationPost.ts, tools/pair-control/src/executor/taskAssign.ts, tools/pair-control/src/executor/contractStorage.ts, tools/pair-control/src/executor/prepareWorktree.ts, tools/pair-control/src/executor/taskApproval.ts, tools/pair-control/src/executor/taskIntegration.ts, tools/pair-control/src/executor/mainDispatch.ts, tools/pair-control/src/executor/mainRole.ts, tools/pair-control/src/executor/actionDispatch.ts, tools/pair-control/src/runtimeServiceTick.ts, tools/pair-control/test/control.test.ts, tools/pair-control/test/api-finalization.test.ts, tools/pair-control/test/api-git-gate.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-api-finalization-20261107.html.
- forbidden_files: 운영 설정/상태/장부·.claude/·모델/worker·사진/라벨/진척·다른 worktree/서버. 실제 모델 요청/학습/추론 금지.
- contract: 자동 행동의 origin을 서비스까지 전달하고 기존 approvalGate의 authorize 또는 validateOrigin 재사용. 수동 요청은 자동 승인 장부를 새로 요구하지 않으며, 동결/메인 세대/stop/guard와 현재 작업 상태는 최종 변경 직전 확인. 이미 시작한 계약 커밋 등 부분 결과는 삭제/이력 재작성하지 않고 재사용 가능하게 보존.
- structure: 시작270파일/783정의·파일당최대7·실제전이4. 새 호출 경로를 직접 측정하며 승인식 복제·콜백/async로 깊이 숨기기 금지.
- checks: 임시 Git wrapper로 준비 대기 중 변경 반례 재현 → 관련 회귀/typecheck/structure --check → 전체 회귀 → main 관련 검증/구조·일반 push·원격 SHA 대조. HTML 실제 렌더·.claude 해시·worktree 보존 기록.
- experiment: 없음. 실제 모델 호출0 유지.
- rollback: 후속 문서부터 역순 git revert·관련 검사·일반 push. reset/force/운영 장부 삭제/결과 불명 재실행 금지.

## 변경 경계
- 작업 승인 기록, 인계 확인 기록, Git cherry-pick 시작, 새 worktree 생성, 계약 파일 쓰기/커밋 시작, 작업 등록, 메인 표시 변경 각각의 마지막 await 뒤 현재 맥락을 확인한다.
- 기존 계약이 이미 커밋된 뒤 메인이 바뀌면 등록만 차단하고 커밋/브랜치는 보존한다. 실행 중 요청을 되감아 같은 작업을 자동 재실행하지 않는다.

- 구조 검사에서 API의 validateOrigin 중간층을 거친 경로2개가5전으로 확인됐다. 승인 함수 authorize의 기존 실행 맥락 책임에 선택적 generation/lifetime 검사를 넣고, workflow용 validateOrigin은 같은 단일 구현에 위임한다. 도메인 변경 경계는 authorize를 직접 호출하며 승인식/세션 판정 복제 없이4전을 유지한다.

- 전체 회귀에서 기존 control.test.ts의 가드 뒤 배정 가정1건이 실패했다. 가드 전 task-b를 배정해 시작 차단 검사를 유지하고, 가드 뒤 task-c 새 배정 거부를 추가 확인한다. 가드를 완화하거나 실패를 제외하지 않고 전체 검사를 다시 실행한다.

## 최종 검증·인계

- 제품/회귀 소스 SHA: 8352bb51416836cd9e869bd4e7d88f88c1bade96
- 적용 순서: 7a3b217845da994a31fd36800eb4813fc6a98c56 → c1f783b30c67e188f1f50f8dfb4eb4fb0ef4d741 → a97e1453dacca50484816f78eb5ee975ef16158b → 7f4a05bb720abceff90059eb5bab40235d1864c7 → 3709607e9d67b9137e559b0edd9257716fdc65ed → 7d44037995dad2eddc7b04ce497a3a0e8cc5cdf6 → 8352bb51416836cd9e869bd4e7d88f88c1bade96.
- 전체320/319통과/0실패/기존건너뜀1. 신규28개 통과. 타입/구조 검사 branch·main 통과, main 관련 회귀 로그 보존. 초기 전체1실패는 가드 뒤 배정을 허용한 구 테스트를 새 배정 차단/기존 작업 시작 차단 모두 검증하도록 수정 후 전체 재실행.
- 구조270파일/783정의·파일최대7·실제전이최대4·초과0·순환0. 변경 파일 정의 수는 HTML 표 참고. 원시 미확인86 동일·실제 출처 대조 후 미분류0(동일 개발자 검토). 외부2740→2741(표준 CheckRun[] push1개).
- 변경: 최종 대기 뒤 세대/수명/동결/stop/가드·단일 approvalGate 승인 재검사, 작업/검사/계약 변경 차단, 계약 배타적 쓰기·부분 커밋 재사용, origin 전달 실경로 회귀.
- 4개 가짜 CLI 절차: 양방향 인수2/연속 턴2/임시 통합2/push0, 원자적 예산. 새 실제 모델 호출0. 절차 초안 실패와 수정 후 통과 근거 보존.
- 산출물: docs/collaboration/reports/pair-control-api-finalization-20261107.html; artifacts/pair-control-api-finalization-20261107/의 로그·audit·verification·SHA256·native-smoke-plan. HTML IAB 열기·실제 렌더 확인 완료·스크린샷 보존.
- .claude/ 해시 전후 동일: c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da. 운영 서버/설정 보존. worktree 제거0·비기본8유지. 원격 결과는 final-remote.json에 기록.
- 미검증: 현재 버전의 실계정 메인 교대·연속 턴·추가 크레딧 꺼짐·잔여 한도. 모델 성능 미평가. 실제 CLI 과거 구현/리뷰 근거는 별도 보존하며 재실행하지 않음.
- 리스크/롤백: 공통 stop/가드 뒤 상태 변경 거부. 이미 시작한 Git 작업 부분 결과 보존. 외부 Git 프로세스 전역 원자성 미보장. 후속 문서부터 역순 git revert·관련 검사·일반 push.
