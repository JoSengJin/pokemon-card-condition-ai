# Codex에게 붙여 넣을 프롬프트

AGENTS.md와 docs/collaboration/CODEX_HANDOFF_RULE_GUARD_20261124.md를 끝까지 읽어라. 코드 수정·실험·push·worktree 삭제는 하지 말고, `git fetch` 뒤 실제 상태와 대조해 다음만 답하라: (1) origin/main SHA와 문서의 커밋 존재 여부, (2) `claude/rule-guard-20261124` branch와 worktree가 남아 있는지, (3) GitHub main에서 force push가 서버에서 거절되도록 설정됐다는 점과 Codex에는 Claude 훅이 적용되지 않는다는 점을 확인했는지, (4) 문서와 실제가 다른 점. 확인하지 못한 것은 미확인으로 써라.
