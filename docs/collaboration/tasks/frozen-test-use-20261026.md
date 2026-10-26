task_id: frozen-test-use-20261026
owner: Codex
status: implementing
base_sha: d7adcf84aa6c4912c06dac0008007149c55f6684
branch: codex/frozen-test-use-20261026
goal: test-only manifest·사진·제공 개발이력을 봉인한 뒤 SHA 고정 입력으로만 평가하고, 같은 실물/사진을 봉인 복제·다른 후보·다른 평가기에서 재사용하면 추론 전에 차단한다.
allowed_files:
- card_condition/frozen_test.py
- card_condition/frozen_test_cli.py
- card_condition/region_evaluation.py
- card_condition/side_evaluation.py
- card_condition/observation_heldout.py
- card_condition/cli.py
- tests/test_frozen_test.py
- tests/test_frozen_test_evaluation.py
- docs/collaboration/tasks/frozen-test-use-20261026.md
- docs/collaboration/reports/frozen-test-use-20261026.md
- ignored artifacts/frozen-test-use-20261026/index.html
- ignored artifacts/frozen-test-usage/ (실행 사용기록)
forbidden_files: 그 외 파일, Claude 데이터확보/페어제어 소스, 데이터/라벨/기존실험/진척률/기준/PokeCollector/비밀설정
contract:
- 기존 manifest 스키마와 loader를 사용한다. test-only·비어있지않은 개발history·ID/group/raw 및 decoded사진 중복 거절. manifest·사진·사람정답·실물group 해시를 보존한다. 내용을 추정/정정/전환하지 않는다.
- 생성한 봉인파일 SHA를 평가시 명시해야 한다. 모든 입력해시가 일치해야 하며 보고서에 봉인·사용영수증을 식별한다. 기존 CLI/API는 추가인자 없으면 동작을 유지한다. side regression에 봉인인자를 쓰면 거절한다.
- 실제 사용기록은 기본checkout artifacts/frozen-test-usage에 flock 직렬화+atomic no-overwrite로 저장한다. 이전 사용과 실물group/decoded사진 중복이면 새 봉인·파일복사·후보변경도 거절. 구현 worktree에서는 실제평가 금지, 테스트는 ledger 경로를 mock한다.
- claim은 추론 직전에 영속한다. 이후 실패해도 시험 노출 가능성이 있으므로 자동 재시도/claim 삭제를 하지 않는다. 기존 경로의 전역 재사용을 강제로 차단한 것은 아니다(옵트인 경로와 이 checkout ledger의 보장).
- 봉인은 무결성/사용이력만 보장한다. 인간 독립성·출처·충분한 전범위분모·하위군·checkpoint 선택 전 시점 증명은 별도 필요. d1_verified/d2_verified false, 진척점수 불변.
structure: frozen_test.py 신규 최대7함수, frozen_test_cli.py 신규1함수. 기존 evaluator 각1→1, cli1→1. 신규경로 evaluator→claim_test→read_seal→file_sha256(3전이); seal_test→load_manifest 및 기존 provenance helper(기존 data 경로). ledger 처리에 추가 wrapper/재귀 없음.
checks: 표준라이브러리 claim/tamper/concurrent/reuse 합성 검사, 기본checkout 기존 fixture를 사용한 실제 manifest 봉인+mock evaluator/CLI 연결, diff/AST, HTML 생성/내용대조/열기. 새 실제학습·실사진추론·외부AI0.
experiment: 없음. 합성/mock 계약검사만 수행한다.
handoff: 실제 결과/구조/리스크/롤백/원격상태를 완료시 기록한다.
