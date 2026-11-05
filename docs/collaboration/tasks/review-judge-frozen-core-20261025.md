# 심판 요약 입력과 동결 원본 분리

- task_id: `review-judge-frozen-core-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `1436e62` (main)
- branch: `codex/review-judge-frozen-core-20261025`
- goal: 저장된 6fbd 검토를 NVIDIA 심판부터 재개한다.
- allowed_files: `card_condition/cross_review_flow.py`, `card_condition/cross_review_nemotron.py`, `tests/test_cross_review_nemotron.py`, 이 문서.
- change: shared_core 검사는 동결 원본 packet으로 유지하고 judge_input에만 32KB 이내 요약 packet을 넘긴다. 호출 상한·중복 키·롤백·평가 기준은 유지한다.
- check: 요약본과 원본 근거가 다른 mock에서도 동결 검사 후 심판 요청까지 도달함. 실제 API 호출 없이 검증.
- rollback: 이 커밋을 되돌리면 종전 연결로 복원되지만 심판 재개에서 동결 검사 오류가 재발한다.
