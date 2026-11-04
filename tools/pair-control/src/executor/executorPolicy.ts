import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';
import type { Agent } from './mainTypes.ts';

export function limitFor(taskExecutor: Executor, agent: Agent): { at: string; detail: string } | null {
  return taskExecutor.state.limit ?? taskExecutor.runtime.limited[agent] ?? null;
}

export function assertMainActive(taskExecutor: Executor, op: string) {
  if (taskExecutor.runtime.frozen) throw new UserError(`메인 교대 중 — ${op}을(를) 지금 할 수 없음(인수 확인 후 새 메인만 진행)`);
}

export function clearLimit(taskExecutor: Executor, ) {
  if (!taskExecutor.state.limit) throw new UserError('한도 도달 상태가 아님');
  taskExecutor.audit('limit_cleared', { was: taskExecutor.state.limit.at });
  taskExecutor.state.limit = null;
  taskExecutor.store.save();
  return null;
}
