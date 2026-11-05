# 교차 검토의 정확한 코드 인용

- task_id: `review-exact-citation-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `7a15d874e28704f38d9d46d8075dccdfeafc80c6`
- branch: `codex/review-exact-citation-20261025` (분리 worktree)
- goal: Codex 교정 입력이 연속된 코드 원문만 `code_checks.quote`로 인용하게 안내하고, 기존 인용 검사는 그대로 유지한다.
- allowed_files: `card_condition/cross_review_auto.py`, `card_condition/cross_review_auto_contract.py`, `tests/test_cross_review_exact_citation.py`, 이 문서.
- forbidden_files: 모델·worker·평가·라벨·비밀 설정·기존 검토 기록.
- contract: `codex_task`의 verify/correct 안내 문구만 변경한다. `quote`의 실제 원문 포함·SHA 검증과 32KB 입력 상한, 호출 상한, 중복 방지, 롤백은 유지한다.
- structure: `cross_review_auto.py` 함수 정의 5→5(중첩 포함), `cross_review_auto_contract.py` 함수 정의 3→3. 새 테스트 함수 1개. 주요 경로 `codex_task → review_context → source_context`, 기존 호출 경로와 깊이 변화 없음.
- checks: 저장된 잘못된 인용이 실제 파일·입력 어디에도 없는 것을 확인. 관련 mock 46개 통과; 실제 실패 입력 재구성 31,329/32,000 bytes. 새 AI 호출 없이 검사.
- experiment: 없음. 새 AI 호출·모델 학습 없이 먼저 테스트한다.
- handoff: 본 branch 커밋을 main에 cherry-pick할 때만 실제 실행에 반영된다. 이번 저장 응답은 잘못된 합성 인용이므로 수정·재사용하지 않는다. main 통합 후 `--fresh`로 새 실행해야 한다. 저장 검토·Gemini 호출 중복 방지 기록은 보존한다. 잔여 위험: 프롬프트는 모델의 정확한 인용을 보장하지 않으므로 기존 검증기가 계속 차단할 수 있다. 롤백은 통합 커밋 revert.
