# worker-only 검토 입력 상한 회귀 보완

- task_id: `worker-only-input-budget-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `712cb89` (main)
- branch: `codex/worker-only-input-budget-20261025`
- goal: 통합된 worker-only 안내가 최신 prompt·규칙과 함께 32,000 bytes 상한을 넘지 않게 한다.
- allowed_files: `card_condition/cross_review_auto.py`, 이 문서.
- change: 중복된 worker 설명 두 문장을 한 문장으로 줄였다. `implementation_files`에는 허용된 모델 소스만 넣고 worker는 별도 출력이며 `worker_importable` 인자 실험에는 빈 목록도 유효하다는 계약은 유지한다. 상한·호출 수·중복 방지·롤백 로직은 변경하지 않았다.
- check: 저장된 978cc `packet.json`·correct payload를 현재 코드의 `codex_task`와 가짜 backend로 재구성해 32,022/32,000 bytes 차단을 확인했다. 수정 후 31,887/32,000 bytes, 차단 없음. worker-only·app-server 모의 테스트 16개 통과. 실제 AI 호출 없음.
- risk: 근거·규칙 문구가 더 길어지면 여유 113 bytes가 다시 소진될 수 있다. 새 자료의 크기까지 보장하지 않는다.
- rollback: 이 커밋을 역순 `git revert`하면 원래 문구로 복원된다. 현재 978cc 입력에서는 사전 차단이 재발한다.
