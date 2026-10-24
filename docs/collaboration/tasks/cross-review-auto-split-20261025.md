# Cross-review auto module split

- task_id: `cross-review-auto-split-20261025`
- owner: Codex
- status: implementing
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
