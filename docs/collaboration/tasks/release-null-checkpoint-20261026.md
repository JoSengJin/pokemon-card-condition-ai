task_id: release-null-checkpoint-20261026
owner: Codex
status: implementing
base_sha: a38cbdb9f5ada69da599c5e0d9a62775c4821505
branch: codex/release-null-checkpoint-20261026
goal: release.checkpoints.region=null 시 CLI의 uncaught KeyError를 없애고, 선언된 모든 checkpoint의 null을 추론 전에 기존 ValueError/JSON 오류 계약으로 거절한다.
allowed_files:
- card_condition/release.py
- tests/test_release_null_entries.py
- docs/collaboration/tasks/release-null-checkpoint-20261026.md
- docs/collaboration/reports/release-null-checkpoint-20261026.md
- ignored artifacts/release-null-checkpoint-20261026/index.html
forbidden_files: 나머지 소스/실자료/라벨/기존실험/진척/기준/소비서비스/Claude소유파일
contract:
- checkpoints의 필수region 키는 그대로필수. optional observation/recall 키생략은기존대로허용. 키를선언했으면값은file/sha256 object이어야하며None은거절한다. 잘못된입력을전체CLI catch확대로숨기지않고read_release경계에서차단한다.
- CLI stderr JSON, requires_gemini=true, exit1, stdoutempty, 모델로딩0. 올바른checkpoint/version/SHA계약은유지한다.
- 재현: 기본checkout에서합성null manifest와mock RegionAnalyzer로 uncaught KeyError 'region', model_load_calls0확인(2026-10-26).
structure: release.py3→3함수. 신규검사<=7함수. 호출경로변경없음.
checks: null3역할/optional생략/기존SHA거절/공용CLIJSON오류·모델로딩0 합성검사. 실제모델학습·추론·외부AI0. diff/AST/HTML/main/push.
experiment: 없음
handoff: 완료시실행검사·리스크·롤백기록.
