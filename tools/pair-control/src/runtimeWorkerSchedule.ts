import { workflowTick } from './runtimeWorkflowTick.ts';
import { serviceTick } from './runtimeServiceTick.ts';
import type { Executor } from './executor/executor.ts';

export function ensureRuntimeWorkers(ex: Executor) {
  if (ex.runtimeTimers.length || ex.stopped) return;
  ex.runtimeTimers = [setInterval(workflowTick, 50, ex), setInterval(serviceTick, 50, ex)];
  for (const timer of ex.runtimeTimers) timer.unref();
}
