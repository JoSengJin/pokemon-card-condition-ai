import { SHARED_CONFIG, DEVELOP_LOCK_PREFIXES } from './contractConstants.ts';
import { pathsOverlap } from './contractPaths.ts';
import type { TaskInputT } from './contractTaskSchema.ts';

export function effectiveGroups(t: Pick<TaskInputT, 'allowedFiles' | 'conflictGroups'>) {
  const g = new Set(t.conflictGroups);
  for (const file of t.allowedFiles) for (const shared of SHARED_CONFIG) if (pathsOverlap(file, shared)) g.add('shared-config');
  return [...g];
}

export function needsDevelopLock(t: Pick<TaskInputT, 'allowedFiles'>) {
  for (const file of t.allowedFiles) for (const prefix of DEVELOP_LOCK_PREFIXES) if (pathsOverlap(file, prefix)) return true;
  return false;
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
