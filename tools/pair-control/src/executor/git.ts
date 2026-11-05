// 공개 API: 책임별 구현을 직접 내보낸다.
export { type Exec, run, git } from './gitProcess.ts';
export { FULL_SHA, revParse, currentBranch, isAncestor, operationInProgress } from './gitRefs.ts';
export { worktrees } from './gitWorktrees.ts';
export { dirtyFiles, changedFiles, diffText } from './gitFiles.ts';
export { commitsBetween } from './gitCommits.ts';
