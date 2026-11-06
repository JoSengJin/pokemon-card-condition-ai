import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';
import type { Agent } from './mainTypes.ts';

export function limitFor(taskExecutor: Executor, agent: Agent): { at: string; detail: string } | null {
  return taskExecutor.state.limit ?? taskExecutor.runtime.limited[agent] ?? null;
}

export function assertMainActive(taskExecutor: Executor, op: string, generation?: number) {
  if (taskExecutor.stopped) throw new UserError(`실행기가 정지됨 — ${op}을(를) 지금 할 수 없음`);
  if (taskExecutor.guardAlert) throw new UserError(`무료 가드 발동 상태(과금 신호) — ${op}을(를) 지금 할 수 없음`);
  if (generation !== undefined && taskExecutor.runtime.generation !== generation) throw new UserError(`메인 세대가 바뀜 — ${op}을(를) 다시 확인해야 함`);
  if (taskExecutor.runtime.frozen) throw new UserError(`메인 교대 중 — ${op}을(를) 지금 할 수 없음(인수 확인 후 새 메인만 진행)`);
}

export function clearLimit(taskExecutor: Executor, ) {
  if (!taskExecutor.state.limit) throw new UserError('한도 도달 상태가 아님');
  taskExecutor.audit('limit_cleared', { was: taskExecutor.state.limit.at });
  taskExecutor.state.limit = null;
  taskExecutor.store.save();
  return null;
}
