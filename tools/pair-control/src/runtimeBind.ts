import type { Mastra } from '@mastra/core/mastra';
import type { Executor } from './executor/executor.ts';
import { setRuntime } from './runtimeCore.ts';
import { ensureRuntimeWorkers } from './runtimeWorkerSchedule.ts';
import { resumeStep } from './runtimeTasks.ts';

export function bindRuntime(ex: Executor, mastra: Mastra) {
  setRuntime(ex, mastra);
  ex.resumer = resumeStep;
  ensureRuntimeWorkers(ex);
}
