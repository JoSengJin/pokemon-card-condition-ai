# pair-control 현재 동작 안내 정정

- task_id: pair-control-ui-guidance-20261106
- owner: Codex
- status: integrated
- base_sha: b3ce3814332d81c0952cd7283a18d7a765b097c5
- branch: codex/pair-control-ui-guidance-20261106
- goal: 표시만 이양하는 수동 기능과 승인 장부를 검사하는 실제 교대를 화면/README에서 구별하고, 이미 끝난 CLI 메타데이터 검증을 미실행으로 안내하지 않는다.
- allowed_files: tools/pair-control/src/ui/page.html, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-ui-guidance-20261106.html.
- forbidden_files: 실행/승인 로직·운영 설정/장부·.claude·모델/worker·사진/라벨/진척·다른 checkout/서버. 실제 모델 호출·학습·추론 금지.
- contract: PAIR_CODING §7·mainAck/approvalGate/mainRole 실제 구현·이미 커밋된 CLI 메타데이터 검증 결과에 맞춰 설명만 정정. 승인·무료 조건을 확대하지 않음. 현재 사용자와 도구 밖 수동 행동의 권한까지 강제한다고 주장하지 않음.
- structure: page.html 함수 정의0→0(인라인 try/변수 선언만 존재, HTML은 trace 대상 아님), 전체270파일/781정의/최대7·실제전이4 유지.
- checks: 이전/후 문구 근거 대조, 관련 UI 회귀(typecheck·구조 포함), 실제 브라우저 안내/버튼 확인·HTML 보고서 렌더. main 관련 검사·.claude 해시·잠금/프로세스 확인·일반 push·원격 SHA 대조. 문구 변경으로 전체 회귀/실제 모델 협업을 새로 검증했다고 보고하지 않음.
- experiment: 없음. 전체 장부78/100 및 모델 성능 변화 없음.
- rollback: 후속 커밋부터 역순 git revert 후 관련 검증·일반 push. 운영 상태 삭제/결과 불명 재실행 금지.

## 읽기 근거
- page.html 메인 안내는 모든 기능을 표시/기록으로만 설명하며 규칙 예외가 필요하다고 한다. PAIR_CODING §7은 역할 교대를 허용하고 mainAck는 실제 인수 뒤 세대·메인을 바꾸며 approvalGate는 수행 범위를 검사한다. 표시만 이양은 mainRole의 별도 경로다.
- README의 옛 단락은 CLI 미설치/로그인 확인 없음이라고 단정하지만 같은 파일의2026-11-06단락과 커밋된cli-readiness보고서에는 version/help/Codex로그인 메타데이터 확인 근거가 있다. 과거 이력과 현재 미검증(실제 모델 요청/교대/추가 크레딧 확인)을 분리한다.

## 인계
- 순서 b3ce3814332d81c0952cd7283a18d7a765b097c5 → 계약 63e4cd283b161e8c3a9083d689f1780758f42e30 → 안내 d7cdaf80463dbab25a3517d1e80d0a8b869c468a → 후속 문서. page.html 메인 안내1단락·README의 관련5곳을 정정, 실행/승인/무료 조건 로직 미변경.
- 분리 브랜치·main 각각 UI관련21개 중20통과/실패0/기존 Playwright 건너뜀1. 실제 ui-theme.test.ts 경로로 테마 검사 포함. 두 위치 typecheck·구조 --check 통과. 전체회귀 재실행 없음.
- 실제 제품 화면 합성 GET 서버에서 안내·기존 버튼·현재/실패 턴 각각1회 유지 확인, 스크린샷/AX 보존. HTML IAB 열기·첫 화면 실제 렌더 확인 완료, 스크린샷 보존.
- HTML은 함수정의0→0이며 trace 대상 아님. JS/TS/scripts270파일/781정의/최대7·실제전이4, 전체trace 불변. 미확인86/native근거분류 미완료0/외부2735, 근거 파일 해시 전부 동일.
- .claude 해시 c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da 불변. 운영 설정/장부/기존 서버 미변경, 실제 모델 호출/학습/추론0. checkout제거0·보존8개. 전체 장부78/100 유지.
- HTML docs/collaboration/reports/pair-control-ui-guidance-20261106.html, 증거 artifacts/pair-control-ui-guidance-20261106/. 롤백은 후속 문서→안내 역순 git revert·관련검증·일반push. 실제 CLI 프롬프트/교대/무료계정조건 미검증은 유지.
