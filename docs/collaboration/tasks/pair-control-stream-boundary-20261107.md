# 관제 스트리밍 로그 청크 경계 보완

- task_id: pair-control-stream-boundary-20261107
- owner: Codex
- status: ready_for_review
- base_sha: f2fd68a34ad824c204e1f2190d16864e24e9e9bd
- branch: codex/pair-control-stream-boundary-20261107
- goal: 청크로 나뉜 비밀값/UTF-8을 가려 기록하고, 1MB 밖 JSON도 내용 이벤트와 실제 과금 신호를 혼동하지 않는다.
- allowed_files: tools/pair-control/src/executor/supervisorIO.mjs, tools/pair-control/src/executor/supervisor.mjs, tools/pair-control/src/executor/processLog.ts, tools/pair-control/test/stream-boundary.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-stream-boundary-20261107.html, ignored artifacts/pair-control-stream-boundary-20261107/.
- forbidden_files: 실제 모델 CLI/API 호출·설정/운영 상태·다른 서버·.claude/·사진/라벨/모델/학습/추론. 실제 CLI 메타데이터도 이번 수정에 필요 없어 실행하지 않는다.
- contract: stdout/stderr 각각 청크를 줄로 모아 UTF-8을 복구한 뒤 가림. 종료 시 마지막 조각도 가리고 기록. 로그 읽기는 원본 byte offset을 쓰고 JSON 한 줄을 잘라 일반 과금 텍스트로 보내지 않음. 실제 과금/한도 오류와 줄바꿈 없는 일반 텍스트 감지는 유지.
- structure: supervisorIO 기존4정의→최대7, supervisor 기존6→최대7, processLog1→1. 실제 호출 전이4 이내, 예외/비동기 은폐/승인식 변경 없음.
- checks: 합성 청크·임시 파일·가짜 child만 사용한 핵심 반례 → 타입/구조 검사 → 필요한 기존 stream 검사만 선별. 전체320개 반복 안 함. 제품 소스 동일성 확인 후 main 통합·일반 push, HTML 실제 렌더·증거 보존.
- risk: 한 줄이 끝나기 전 로그는 메모리에서 대기하며, 긴 JSON 읽기 메모리는 그 한 줄 크기에 비례한다. 타임아웃/종료 시 잔여 로그는 보존.
- rollback: 변경 커밋 역순 git revert·핵심 검사·일반 push. 운영 상태/미확인 요청 삭제·재실행 없음.

## 체크포인트

- 소스 SHA: 48a716ee85a5a5f83f5be93b78dae65978e21949; 실제 모델/CLI 요청0.
- 핵심10+수명2 총12개 통과, 타입/구조 통과. 전체 반복 안 함. 새6개 반례, 기존6개 선별.
- supervisorIO4→7/supervisor6→6/processLog1→1, 전체270/786정의/최대7/전이4. 콜백→writeChunk/finishLog→writeLog→redact→reduce콜백4전.
- 원시 미확인93, 새7개 Buffer/StringDecoder 타입·생성·실제 호출자·Node 구현 대조. 미분류0, 기존 근거 해시 불변. 외부2747(+11/-5), 예외 추가 없음.
- 기본 checkout 다른 개발 잠금·변경 발견: main 통합 대기, 건드리지 않음. 독립 worktree에서 증거/보고 보존.
- 보고서: docs/collaboration/reports/pair-control-stream-boundary-20261107.html; 증거: artifacts/pair-control-stream-boundary-20261107/. HTML IAB 열기·실제 렌더 확인 완료. 화면 증거 보존.
- 미실행/리스크/롤백: 보고서 참조. 코드소스 검증과 실제 모델/운영 채택을 구분.
