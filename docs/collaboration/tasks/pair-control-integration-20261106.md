# pair-control 후속 통합·복구 검증

- task_id: pair-control-integration-20261106
- owner: Codex
- status: integrated (사용자 지정 보존 조건으로 main 통합·main 전체 회귀·일반 push·worktree 정리 완료)
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

## main 채택 — 사용자 지정 절차 실행 (2026-11-06)
- 사용자 최신 요청이 이전 main 통합 보류와 저장소 main 일반 push 금지를 대체한다. .claude/launch.json 보존 조건으로 통합을 명시 지시했으며 모델 호출·학습·추론 금지는 유지한다. 상시 .claude 예외 문구 추가는 이번 통합과 분리해 실행하지 않았다.
- 기록 범위: 이 계약, 구조 준수 계약의 통합 상태, docs/collaboration/reports/pair-control-main-adoption-20261106.html, ignored artifacts/pair-control-main-adoption-20261106/. 제품·모델·worker 추가 수정 없음.
- 사전 main=origin/main 3c2e0b1882e117fc558073b23a9f543e50ec40fe, 작업 트리 ?? .claude/ 한 줄, 해당 폴더는 미추적 launch.json 하나·ignore 대상 아님. 기준/허용 경로·진행 Git 작업·개발 잠금·관련 실험/자동 검토 실행 부재 확인. 기존 관제 서버와 저장 장부는 읽기 확인만 했다.
- ./develop -- git merge --ff-only codex/pair-control-integration-20261106 성공 → 353319440d3e17d441b51a64970d9e3c7c3b66ea. 소스 채택364파일, .claude 및 .gitignore 변경0. .claude/launch.json을 stage·커밋·이동·삭제·stash·ignore하지 않았다.
- launch.json SHA-256 사전=통합 후=첫 push 후: c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da.
- main에서 npm ci --offline --ignore-scripts --no-audit --no-fund(373패키지, 새 다운로드·설치 스크립트 없음), typecheck 통과, structure --check 통과. 전체 npm test 240개/239통과/실패0/취소0/기존건너뜀1, 678515.176ms. 검사 코드 SHA3533194…이며 이후 문서만 변경한다. 모델/실제 CLI 요청·학습·사진 추론 없음.
- 구조270파일/779정의/파일당 최대7/전이최대4/초과0/순환0. 원시 미확인86·외부2732. 그래프 전체 및 native 감사 근거 파일 해시가 검증 브랜치와 동일함을 main의 새 설치에서 대조했다. 동일 개발자 감사이며 독립 검토가 아니다.
- push 직전 fetch 결과 원격 기준 불변. 일반 ./develop -- git push origin main 성공, ls-remote로 원격=로컬353319440d3e17d441b51a64970d9e3c7c3b66ea 확인. 이후 인계 문서 커밋은 별도로 일반 push·원격 일치를 확인한다.
- 정리: A3 롤백용 checkout과 RCI checkout 2개 일반 remove 성공. 모든 대상의 HEAD/미커밋/Git 작업/process cwd/통합 이력 재확인. A3는 ignored0·기존 잠금 없음. RCI는 .venv 재생성 가능, 설정 정본과 바이트 동일·정본 유지, 기존 workspace.lock flock을 제거 반환까지 유지하고 잠금 증거를 먼저 복사·해시 검증. branch ref 불변, force/clean/reset/stash 없음. RCI 1차 분류는 .venv 때문에 보류했으나 파일 목록 대조 후 재생성 환경으로 확인해 제거했다.
- 유지8개: 최신 완료 Codex pair-control1개, 전체 커밋 대응 미확정5개(adopt-train/card-corner/data-coverage/mobile-label/task-1026-1), 미추적 구현이 있는 normal-coexclusion1개, 서버 사용 중 Claude pair-control1개. 앱 관리 최신 worktree는 유지하며 archive/수동 삭제하지 않았다.
- 고유 RCI 잠금 증거: artifacts/pair-control-main-adoption-20261106/worktrees/pokemon-card-condition-claude-rci/workspace.lock, SHA-256 716e7514416ffd04028826f283af7053b43047599c4030b13587d08cd87f53c4. 나머지 로그·감사는 SHA256.json/adoption.json에 보존(ignored). 설정 비밀값은 복사/보고서 노출하지 않았다.
- 남은 검증: Playwright 미설치 자동 UI1건 건너뜀, 실제 CLI 인증/교대 환경과 실제 main rollback 미실행. 합성/fake CLI/임시 bare 검증과 구분한다. 모델 정확도 변화 미평가, 전체 장부 usable-card-analysis-v1.13 78/100 유지.
- 롤백: reset --hard 미실행·별도 승인 없이 사용 금지. 실제 필요 시 최종 인계 문서 커밋부터 역순 revert, 이후 353319440d3e17d441b51a64970d9e3c7c3b66ea → 9629e2c0f5cc7e83328af8f3ab9aa81caef6509e → b8fa28dbf186cb053cb67364241e5a30d8fc512e 순서, 마지막 d9aa5255f11c875b8f4eb38d21000c79eb50d0b9는 기존 main인 두 번째 부모 기준 git revert -m 2. 충돌은 검토하며 .claude/ 보존·재검증 후 일반 push. 복구를 실제 실행했다는 뜻은 아니다. 제거한 checkout은 보존 branch로 git worktree add, RCI 설정은 정본 해시 대조 후 복원하고 환경 재생성한다.
- main 채택 HTML 실제 브라우저 렌더 확인: 첫 화면의 코드SHA3533194…·240/239/0/1·구조초과0·worktree2개정리·설정해시불변을 대조했고 오류/경고0. 스크린샷 pair-main-adoption-report-20261106.png, SHA-256 8e9662a6ad35300a437f905c8e4e8f5e828fb9e79d55c7212fbec2bf0addb93e. 보고서·검사·감사 증거는 ignored artifacts/pair-control-main-adoption-20261106/에 보존.
