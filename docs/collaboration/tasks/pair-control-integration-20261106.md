# pair-control 후속 통합·복구 검증

- task_id: pair-control-integration-20261106
- owner: Codex
- status: ready_for_review (후속 브랜치 검증 완료, 기본 checkout 미추적 파일로 main 통합 보류)
- base_sha: c4179271756645882b917c417ac96f97578fa355
- integration_base_sha: 3c2e0b1882e117fc558073b23a9f543e50ec40fe (fetch 확인 main=origin/main)
- branch: codex/pair-control-integration-20261106
- goal: 최신 main과 도구 전체를 별도 브랜치에서 결합·검증하고 실행 직전 stop/승인 철회 반례를 보완한다.
- allowed_files: 이 계약, docs/collaboration/reports/pair-control-integration-20261106.html, tools/pair-control/src/executor/taskLaunch.ts, tools/pair-control/src/executor/taskSpawn.ts, tools/pair-control/src/executor/taskReserve.ts, tools/pair-control/src/runtimeServiceTick.ts, tools/pair-control/src/runtimeRequests.ts, tools/pair-control/src/runtimeRequestPolicy.ts, tools/pair-control/test/launch-authority.test.ts, tools/pair-control/test/control.test.ts. 최신 main 병합 유입 파일은 기존 커밋 그대로 보존하고 AGENTS.md/PAIR_CODING.md/README.md 충돌만 양쪽 지침·도구 안내를 대조해 해결한다.
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

## 연결·중단 검증 보완
- 병합 SHA: d9aa525 (전체 SHA는 최종 인계에 기록). 코드 충돌 없음. AGENTS/PAIR_CODING은 최신 구조·증거 보존 지침과 기존 §7 승인 승계를 함께 보존했다.
- 재현: 사전 검사 대기 중 stop 뒤 launch가 ok:true로 프로세스를 시작함. 실패 로그 pair-launch-authority-before-fixed-fixture-20261106.log(세션 로컬 /tmp). 최초 테스트는 fixture ID 오타로 별도 실패했고 원인 재현과 구분했다.
- taskReserve는 stop 상태의 예약 거절, taskLaunch는 preflight 뒤·probe/startPrompt 뒤 validateOrigin 재검사와 과금 가드/공급자별 한도 재검사, runtimeServiceTick은 저장 origin을 launch까지 전달한다. 승인식은 approvalGate 그대로 사용한다.
- 새 회귀12개: stop·철회·세대·세션·동결, CLI 탐색 대기 중 stop·철회·한도·가드, worker origin 전달, 유효 origin 정상 시작. 모두 fake CLI/합성 임시 저장소만 사용.
- typecheck 통과. 관련 저장 요청9개 포함 총21개 통과/실패0, 19747.827208ms. pair-integration-targeted-20261106.log.
- taskLaunch 정의7→7, taskReserve1→1, runtimeServiceTick1→1. 전체270파일/779정의 불변, 최대전이4 유지, 초과파일0/시작점0/순환0. serviceTick→launch→validateOrigin→authorize→unmet=4. 원시 미확인86, 외부호출2730→2732(검사 메시지 내 Error2개) — 최종 분류 대조 예정.
- 전체 회귀/최종 HTML은 다음 단계이며 아직 이번 결과로 보고하지 않는다.

## 첫 전체 회귀의 비동기 관찰 경합
- b8fa28dbf186cb053cb67364241e5a30d8fc512e 전체240개: 238통과/1실패/1기존 건너뜀, 673910.643375ms. 실패는 control.test.ts:59에서 status=review_pending 저장 직후 Mastra suspendedStep=null을 읽은 경우다. 분리 실행1개는 통과했으나 전체 실패를 성공으로 대체하지 않았다.
- collect 서비스의 작업 상태 저장과 native review-gate suspend 저장은 독립된 비동기 단계다. 임의 지연·기대값 완화 없이 runInfo.suspendedStep=review-gate가 실제 저장될 때까지 기존 waitFor로 기다린다. control.test.ts의 이 검증 지점만 수정한다. 운영 소스는 변경하지 않는다.

## 최종 검증·인계
- 적용 순서: 460d16d03a96b2ce7d9b8036d1cc31fda0537547(후속 계약) → d9aa5255f11c875b8f4eb38d21000c79eb50d0b9(main 3c2e0b1882e117fc558073b23a9f543e50ec40fe 결합) → b8fa28dbf186cb053cb67364241e5a30d8fc512e(실행 직전 보호) → 9629e2c0f5cc7e83328af8f3ab9aa81caef6509e(실제 review-gate 저장 대기 회귀). 기존 완료 c4179271756645882b917c417ac96f97578fa355 보존.
- 최종 전체 npm test: 총240/239통과/실패0/취소0/기존 건너뜀1, 674079.528584ms. 코드·테스트 SHA 9629e2c0f5cc7e83328af8f3ab9aa81caef6509e. 이후 변경은 이 계약과 HTML뿐이다.
- 최종 로그 pair-integration-full-final-20261106.log(세션 로컬 /tmp), SHA-256 51753512d2fa3be240352dd5025a8df2cff1c2cf011fb6af47849e576409b9dc. 최초 전체 실패 로그 SHA-256 bf1b911e585381131163ba46074961d47ac59b7a0450154b7d1acbdda7ca999b도 보존.
- 관제 핵심 회귀10개 추가 확인: 전부 통과, 43392.77375ms. typecheck/오프라인 npm ls/diff --check 통과. 최종 structure --check 종료0이며 감사 그래프와 동일.
- 구조270파일/779정의/최대정의7/최대전이4/초과파일0/초과시작점0/순환0. 원시 미확인86개는 호출 지점과 모든 근거 파일 해시가 이전 감사와 같음을 대조했다. 동일 개발자 소스 대조 후 미분류0. 외부2732, 행 번호 제외 비교 시 표준 Error 생성2개만 추가.
- HTML docs/collaboration/reports/pair-control-integration-20261106.html 생성. 실제 브라우저에서 SHA·전체240/239/0/1·구조 초과0·변경 표 렌더를 확인했고 브라우저 오류/경고0. 최종 스크린샷 pair-integration-report-20261106.png(세션 로컬 /tmp). 자동 UI 회귀는 Playwright 미설치1건 건너뜀 그대로이며 수동 보고서 렌더를 자동 UI 통과로 바꾸지 않았다.
- 보고서 생성기 최초 실행은 소스 인코딩 선언 오류로 실패했고 UTF-8 선언을 추가한 뒤 생성 성공. 첫 localhost bind는 sandbox 권한으로 실패해 승인된 localhost 정적 보고서 서버로 렌더 확인했다. 실제 provider/운영 상태 변경 없음.
- 남은 의존: 기본 checkout의 미추적 .claude/ 보존 조건과 PAIR_CODING.md §6.2의 깨끗한 checkout 요건이 충돌해 main 통합 보류. 해당 파일 삭제·stash·reset·임의 ignore를 하지 않았다. 이 파일을 그대로 보존한 통합 예외 허용 또는 checkout 정리가 필요하다. 운영 push·실제 모델 CLI 요청은 계속 금지.
- 리스크: 실제 CLI 인증·배포 환경 미검증. 관제·framework 저장 시점은 비동기이며 독립 저장의 완료를 근거로 대조해야 한다. 롤백은 테스트9629e2c…→보호b8fa28d… 순서로 ./develop -- git revert. 기본 main에는 적용하지 않았고 결과 불명 장부를 삭제·재실행하지 않는다.
- 보고서 스크린샷 SHA-256 7ad3e5d4281f87921b46f79ce9e125e3c3850e6ad85737f2d58ae7f90b43a2c0
