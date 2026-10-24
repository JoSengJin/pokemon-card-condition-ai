# Cross-review auto module split

- task_id: `cross-review-auto-split-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `b4d3ddd`
- branch: `codex/cross-review-auto-split-20261025`
- worktree: session-local managed worktree
- goal: split `cross_review_auto.py` into cohesive modules with at most seven function definitions per source file, preserve behavior, then integrate Claude worker-only fix `8aebeb7`.
- allowed_files: `card_condition/cross_review_auto.py`, `card_condition/cross_review_auto_*.py`, `tests/test_cross_review_worker_only_*.py`, this task document, Claude task document.
- forbidden_files: labels, photos, model weights, secrets, experiment artifacts, PokeCollector, other agents' task files.
- contract: preserve public names from `card_condition.cross_review_auto`, stored calls, refusal gates, provider budgets, and rollback behavior. Do not call AI or train. Keep the Claude change limited to worker-only input and corrective error wording.
- structure: source currently has 45 function definitions (including nested); target at most seven per source file. The existing end-to-end graph has deeper preexisting call paths; changed module boundaries must not add a call transition. Verify representative changed paths explicitly; report any unproven global depth instead of claiming compliance.
- checks: worker-only mock tests; cross-review auto, contract, high fixes, stored resume and app-server tests; exact 978cc correct-input byte preflight; no AI calls.
- experiment: none.
- handoff: commit SHA, changed files, tests, unverified behavior, risks and rollback.

## 구현·검사 결과

- `cross_review_auto.py`의 공개 API를 유지하면서 계약, 소스 발췌, 하위 Codex 설정, 입력 구성, 판정 검증(형식/근거/계획), 결과 렌더링을 응집된 모듈로 옮겼다. 실제 검증 순서·오류 문구·중복 호출 차단은 유지한다.
- 각 `cross_review_auto*.py`의 함수 정의(AST, 중첩 포함): 5, 6, 1, 3, 6, 6, 2, 5, 5, 5개. 모두 7 이하. 기존 `_run_auto` 전달 래퍼는 제거해 자동 검토 진입 경로를 한 단계 줄였다. 전체 저장소 호출 깊이 4 이하를 증명한 것은 아니며, 기존 경로 중 더 깊은 곳은 별도 구조 감사가 필요하다.
- Claude 수정의 worker-only mock 7개와 관련 검토 52개 통과. 전체 717개 중 714개 통과; 나머지 3개는 격리 worktree에 Git 제외된 평가 artifacts가 없어 FileNotFoundError였다. 같은 3개 테스트는 기본 checkout의 해당 자료로 각각 통과했다. macOS sandbox-exec가 이 Codex 샌드박스에서 시작되지 않아 격리 실행 24개는 실행 가능한 권한 환경에서 재검사했고 전부 통과했다.
- 저장된 `978cc047dc49`의 correction payload digest `01e63b4f631387af`를 mock backend로 재구성한 Codex preflight는 31,809/32,000 bytes였다. 실제 Codex 응답은 검증하지 않았다. 여유 191 bytes로 여전히 작다.
- 실제 Codex·Gemini·NVIDIA 호출, 학습, 사진 추론 없음. 성능 변화 미측정.
- 위험: 새 모듈이 격리 worker에 함께 있어야 하는 import 경계, 좁은 입력 크기 여유, 기존 저장 `stopped` 응답의 재사용. rollback: 통합 커밋을 `./develop -- git revert <SHA>`로 되돌리고, 사용자 미커밋 문서는 보존한다.
