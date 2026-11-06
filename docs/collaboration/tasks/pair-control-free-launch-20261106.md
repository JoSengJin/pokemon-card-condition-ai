# pair-control 무료 조건 실행 경로 루프 보완

- task_id: pair-control-free-launch-20261106
- owner: Codex
- status: integrated
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

## 검증·인계
- 적용 순서: 07079575faac6b66eddd4be02d594fc737ca1b78 → 계약 430c090fe81a391645e645b17f87c33015226910 → 코드 2f9d4f01182ea1da5b911f9a4c95cee818db34ee → 후속 문서 커밋. 코드 변경은 위 4파일과 test/free-launch.test.ts·README.md다.
- 수정 전 fake 반례13개 실패 → 수정 후13개 통과. 분리 브랜치 전체260개/259통과/실패0/기존 건너뜀1. main 관련 검사 결과는 HTML 및 artifacts/pair-control-free-launch-20261106/ 로그와 SHA256.json 참조. main 전체260개 재실행은 하지 않았다.
- typecheck·구조 --check 두 위치 통과.270파일/780정의/최대7/실제전이4/초과0/순환0. taskLaunch7→7, reviewStart5→5, executor7→7, codexSettings2→2. launch 최대3전·review와 main 시작2전 유지. 공통 무료 검사2전, 승인식 변경 없음.
- 원시 미확인86개 호출 지점과 모든 근거 파일 해시 불변. native 분류 미완료0; 외부2734→2735는 risks.push·blockers.map 추가와 중복 failed.map 제거. 같은 개발자의 근거 대조이며 독립 검토 아님.
- main 잠금/프로세스·최신 기준·.claude 보존 확인. launch.json 전후 해시 c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da 불변, .claude/.gitignore diff 없음. 운영 설정·장부·기존 서버 재시작 없음. 제거0·보존8개, 미통합/미커밋/사용 중 checkout 보존.
- 실제 모델 호출/학습/추론0. 추가 크레딧 꺼짐·실제 CLI 교대/복구 미검증. 보수적 profile 차단으로 무료 설정도 보류 가능. 외부 계정/파일의 동시 변경을 원자적으로 막는 보장은 없음. 기존 서버에는 자동 배포하지 않음. 카드 모델 장부78/100 유지, 성능 미평가.
- HTML: docs/collaboration/reports/pair-control-free-launch-20261106.html. IAB로 열기·첫 화면 실제 렌더 확인 완료, 스크린샷은 Git 제외 증거 폴더에 보존. 제품 자동 UI 건너뜀을 대체하지 않음. 롤백은 후속 문서부터 역순 git revert 2f9d4f01182ea1da5b911f9a4c95cee818db34ee 포함·검증·일반 push. 실제 롤백 미실행, reset/force/장부 삭제 금지.

- main 관련47개/47통과/실패0/건너뜀0(88490.384625ms). 분리 브랜치 전체260개는691829.328792ms. 실행 명령은 HTML에 기록. 문서만 후속 변경했고 소스 재수정 없음. 일반 push·원격 SHA 사후 대조는 final-remote.json과 최종 보고로 확인.
