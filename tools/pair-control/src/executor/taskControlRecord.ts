import { appendEvent } from './store.ts';
import type { Executor, Task } from './executor.ts';

export type Resume = (runId: string, step: string, data: Record<string, unknown>) => Promise<unknown>;

export function record(ex: Executor, t: Task, type: string, data: Record<string, unknown> = {}) {
  t.updatedAt = new Date().toISOString();
  appendEvent(ex.cfg.stateDir, { type, lifetime: ex.lifetime, taskId: t.taskId, ...data });
  ex.store.save();
}
