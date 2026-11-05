import { getTask } from './executorLookup.ts';
import { record } from './taskControlRecord.ts';
import { UserError } from './errors.ts';
import { OCCUPYING, type Executor } from './executor.ts';

export function setArchived(ex: Executor, taskId: string, archived: boolean) {
  const t = getTask(ex, taskId);
  if (archived && OCCUPYING.includes(t.status)) throw new UserError(`진행 중이거나 결정이 남은 작업은 보관할 수 없음(${t.status}) — 먼저 취소·거절하거나 통합하세요`);
  t.archivedAt = archived ? new Date().toISOString() : null;
  record(ex, t, archived ? 'task_archived' : 'task_unarchived');
  return t;
}

export function archiveFinished(ex: Executor) {
  const pushed = new Set(Object.values(ex.state.pushes ?? {}).filter((r) => r.status === 'pushed_verified').flatMap((r) => r.tasks));
  const archived: string[] = [];
  for (const t of Object.values(ex.state.tasks)) {
    if (t.archivedAt) continue;
    if (!(['rejected', 'abandoned'].includes(t.status) || (t.status === 'integrated' && pushed.has(t.taskId)))) continue;
    t.archivedAt = new Date().toISOString();
    record(ex, t, 'task_archived', { bulk: true });
    archived.push(t.taskId);
  }
  return { archived };
}
