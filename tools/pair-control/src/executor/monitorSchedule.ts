import { tick } from './monitorTick.ts';
import type { Executor } from './executor.ts';

export function ensureWatcher(taskExecutor: Executor, ) {
  if (!taskExecutor.timer) { taskExecutor.timer = setInterval(tick, 300, taskExecutor); taskExecutor.timer.unref?.(); }
}

export function stop(taskExecutor: Executor, ) { taskExecutor.stopped = true; if (taskExecutor.timer) clearInterval(taskExecutor.timer); taskExecutor.timer = null; for (const timer of taskExecutor.runtimeTimers) clearInterval(timer); taskExecutor.runtimeTimers = []; }
