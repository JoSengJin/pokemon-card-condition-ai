import { appendEvent } from './store.ts';
import type { Executor, Task, TaskStatus } from './executor.ts';

export function setStatus(ex: Executor, t: Task, s: TaskStatus, reason?: string) {
  t.status = s; t.statusReason = reason; t.updatedAt = new Date().toISOString();
  appendEvent(ex.cfg.stateDir, { type: 'task_status', lifetime: ex.lifetime, taskId: t.taskId, status: s, reason });
  ex.store.save();
}

export function releaseExecLocks(ex: Executor, t: Task, execId: string) {
  for (const n of [`task:${t.taskId}`, `worktree:${t.worktree}`, `branch:${t.branch}`]) ex.locks.release(n, 'execId', execId);
}
