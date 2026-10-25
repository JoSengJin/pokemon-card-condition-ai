# 최신 검토 입력 24KB 초과 수정

- task_id: `review-manifest-dedupe-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `ee6587a` (main)
- branch: `codex/review-manifest-dedupe-20261025`
- goal: 현재 최신 자료를 `./review --auto`의 24KB 사전 검사에 통과시키되 평가 수치·실패 조건·근거 SHA를 그대로 유지하고 실제 AI 호출 없이 검증한다.
- allowed_files: `card_condition/cross_review_evidence.py`, `card_condition/cross_review_evidence_budget.py`, `card_condition/cross_review_evidence_codec.py`, `card_condition/cross_review_evidence_cohort.py`, `card_condition/cross_review_evidence_manifest.py`, `card_condition/cross_review_auto_sources.py`, `card_condition/cross_review_manual.py`, `tests/test_cross_review_manifest_budget.py`, `tests/test_cross_review_app_server.py`, 이 문서, ignored `artifacts/review-input-budget-20261025/index.html`.
- forbidden_files: 모델·worker·평가 정답·기존 검토 원문·비밀 설정.
- contract: `latest_sources` 중 이미 `evidence`에 있는 경로·SHA는 ID 참조로 직렬화한다. 검증·freshness·identity에서 이를 원래 경로·SHA로 펼친다. 기존 완전한 `latest_sources`도 계속 읽는다. 수치·실패 조건·24KB 상한·호출 상한·롤백은 변경하지 않는다.
- structure: 기존 `cross_review_evidence.py`의 함수 17개를 본문 변경 없이 책임별 파일(6/4/7/2개)로 분리한다. 새 manifest 파일은 2개다. 기존 `$ref` 재귀는 원문 그대로 이동하며 새 호출 경로를 추가하지 않는다. 사용자 선택: 이번에는 기존 재귀 유지 후 통합, 재귀 제거는 별도 작업.
- checks: 실제 최신 패킷 24,120→23,700 bytes, 코드 발췌 0→994자. 동결 평가·실패 근거 SHA 동일(`650b548b…`). 가짜 Codex verify 입력 28,247/32,000 bytes. 근거·재개·worker-only mock 61개 통과, 기본 checkout의 artifact 의존 6개 통과. worktree 코드로 전체 검사 798개 중 오류 4개: 3개는 worktree의 Git 제외 artifact 부재, 1개는 시험용 packet이 참조 대상의 경로·SHA를 제거한 fixture 오류였고 수정 후 단독 통과. 기본 checkout 통합본에서 전체 재검사 예정. AI 호출 없음.
- HTML: ignored `artifacts/review-input-budget-20261025/index.html`에 실제 검사와 진척률을 기록하고 열기/렌더 결과를 handoff에 적는다.
- rollback: 통합 SHA를 `./develop -- git revert <SHA>`로 되돌려 직렬화와 모듈 분리를 함께 복원한다. 당시 최신 입력의 24KB 오류는 재발한다.
