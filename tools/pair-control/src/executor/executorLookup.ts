import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export function getTask(ex: Executor, id: string) {
  const task = ex.state.tasks[id];
  if (!task) throw new UserError('task 없음: ' + id);
  return task;
}

export function limitOf(ex: Executor) { return ex.state.limit ?? null; }
