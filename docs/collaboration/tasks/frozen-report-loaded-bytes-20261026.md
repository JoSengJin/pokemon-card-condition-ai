task_id: frozen-report-loaded-bytes-20261026
owner: Codex
status: implementing
base_sha: ec9c84505e2e33456929425f51e78d983f001631
branch: codex/frozen-report-loaded-bytes-20261026
goal: 동결평가 재집계에서 candidate/report/receipt SHA와 실제 JSON 해석 내용이 같은 바이트임을 보장한다.
allowed_files:
- card_condition/evaluation_suite_inputs.py
- tests/test_frozen_report_loaded_bytes.py
- docs/collaboration/tasks/frozen-report-loaded-bytes-20261026.md
- docs/collaboration/reports/frozen-report-loaded-bytes-20261026.md
- ignored artifacts/frozen-report-loaded-bytes-20261026/index.html
forbidden_files: 그 외 소스/실자료·정답·모델/기존 고정기록/기준·진척/Claude 파일
contract: matched_reports의 candidate/report/receipt를 한번 read_bytes한 snapshot으로 hash대조와 json.loads를 함께 수행한다. SHA후 read_text 재개방을 없애고 기존 필드검증/최종 unchanged input 검사/one-use claim/threshold/정답은 유지한다. 새 helper/framework 없음.
structure: evaluation_suite_inputs2→2, 신규검사<=7. 기존 read/hash/json 호출을 치환하며 새 호출깊이 증가 없음.
checks: 기존 helper를 통한 hash검사뒤 read_text 대체로 pinned SHA와 다른 report내용이 found에 반영되는 합성반례. 변경후 세파일 모두 snapshot과 JSON 일치/원본pin불일치거절/실제assess 경로 + 이전126회귀, AST/compile/diff/HTML/main push.
experiment: 없음. 합성 저장 JSON/mock 읽기 대조, 실사진 추론·새학습·외부AI0.
handoff: 변경파일/diff/실검사/미검증/메모리리스크/롤백/원격·HTML.진척30/100 유지.
