task_id: frozen-report-loaded-bytes-20261026
owner: Codex
status: integrated
base_sha: ec9c84505e2e33456929425f51e78d983f001631
branch: codex/frozen-report-loaded-bytes-20261026
goal: 동결평가 재집계에서 candidate/report/receipt SHA와 실제 JSON 해석 내용이 같은 바이트임을 보장한다.
allowed_files:
- card_condition/evaluation_suite_inputs.py
- tests/test_frozen_report_loaded_bytes.py
- tests/test_evaluation_output_safety.py
- docs/collaboration/tasks/frozen-report-loaded-bytes-20261026.md
- docs/collaboration/reports/frozen-report-loaded-bytes-20261026.md
- ignored artifacts/frozen-report-loaded-bytes-20261026/index.html
forbidden_files: 그 외 소스/실자료·정답·모델/기존 고정기록/기준·진척/Claude 파일
contract: matched_reports의 candidate/report/receipt를 한번 read_bytes한 snapshot으로 hash대조와 json.loads를 함께 수행한다. SHA후 read_text 재개방을 없애고 기존 필드검증/최종 unchanged input 검사/one-use claim/threshold/정답은 유지한다. 새 helper/framework 없음.
structure: evaluation_suite_inputs2→2, 신규검사<=7. 기존 read/hash/json 호출을 치환하며 새 호출깊이 증가 없음.
checks: 기존 helper를 통한 hash검사뒤 read_text 대체로 pinned SHA와 다른 report내용이 found에 반영되는 합성반례. 변경후 세파일 모두 snapshot과 JSON 일치/원본pin불일치거절/실제assess 경로 + 이전126회귀, AST/compile/diff/HTML/main push.
experiment: 없음. 합성 저장 JSON/mock 읽기 대조, 실사진 추론·새학습·외부AI0.
handoff: 변경파일/diff/실검사/미검증/메모리리스크/롤백/원격·HTML.진척30/100 유지.

검증 중 계약 보완: 추가34회귀 중2가 NaN mock을 ENOSPC 주입 전 정상으로 복구하지 않아 새 점수 guard에서 먼저 실패했다. 평가 로직을 완화하지 않고 tests/test_evaluation_output_safety.py에서 NaN/ENOSPC fixture를 분리한다. JSON publisher 자체의 부분 NaN 쓰기·임시파일 정리도 기존 test에 직접 대조한다. 기존파일7→7, 새함수·호출깊이 없음.

완료:ddd93db+c3c6025.129+추가34=서로다른163검사PASS.리스크·롤백·미측정은보고서.진척30/100.
