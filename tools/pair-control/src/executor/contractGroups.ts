import { SHARED_CONFIG, DEVELOP_LOCK_PREFIXES } from './contractConstants.ts';
import { pathsOverlap } from './contractPaths.ts';
import type { TaskInputT } from './contractTaskSchema.ts';

export function effectiveGroups(t: Pick<TaskInputT, 'allowedFiles' | 'conflictGroups'>) {
  const g = new Set(t.conflictGroups);
  if (t.allowedFiles.some((f) => SHARED_CONFIG.some((s) => pathsOverlap(f, s)))) g.add('shared-config');
  return [...g];
}

export function needsDevelopLock(t: Pick<TaskInputT, 'allowedFiles'>) {
  return t.allowedFiles.some((f) => DEVELOP_LOCK_PREFIXES.some((p) => pathsOverlap(f, p)));
}

export interface ConflictReason { kind: 'files' | 'group' | 'worktree' | 'branch'; detail: string; otherTask: string }

export function conflicts(a: TaskInputT, b: TaskInputT, groups: { a: string[]; b: string[] }): ConflictReason[] {
  const out: ConflictReason[] = [];
  for (const fa of a.allowedFiles) for (const fb of b.allowedFiles) {
    if (pathsOverlap(fa, fb)) out.push({ kind: 'files', detail: `${fa} ↔ ${fb}`, otherTask: b.taskId });
  }
  const gb = new Set(groups.b);
  for (const g of groups.a) if (gb.has(g)) out.push({ kind: 'group', detail: g, otherTask: b.taskId });
  if (a.worktree === b.worktree) out.push({ kind: 'worktree', detail: a.worktree, otherTask: b.taskId });
  if (a.branch === b.branch) out.push({ kind: 'branch', detail: a.branch, otherTask: b.taskId });
  return out;
}
