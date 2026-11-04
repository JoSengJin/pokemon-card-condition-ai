import { tick } from './monitorTick.ts';
import type { Executor } from './executor.ts';

export function ensureWatcher(taskExecutor: Executor, ) {
  if (!taskExecutor.timer) { taskExecutor.timer = setInterval(() => void tick(taskExecutor, ), 300); taskExecutor.timer.unref?.(); }
}

export function stop(taskExecutor: Executor, ) { taskExecutor.stopped = true; if (taskExecutor.timer) clearInterval(taskExecutor.timer); taskExecutor.timer = null; }
