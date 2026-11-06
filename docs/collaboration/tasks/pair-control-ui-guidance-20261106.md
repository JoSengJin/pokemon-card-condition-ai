# pair-control 현재 동작 안내 정정

- task_id: pair-control-ui-guidance-20261106
- owner: Codex
- status: implementing
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
