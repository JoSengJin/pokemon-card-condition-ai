import { approve } from './executor/taskApproval.ts';
import type { Mastra } from '@mastra/core/mastra';
import type { Executor } from './executor/executor.ts';
import { setRuntime } from './runtimeCore.ts';
import { prepareTask, resumeStep, startTask } from './runtimeTasks.ts';

export function bindRuntime(ex: Executor, mastra: Mastra) {
  setRuntime(ex, mastra);
  ex.setResumer(async (runId, step, data) => { await resumeStep(runId, step, data); });
  ex.setMainOps({
    approve: async (taskId, sha) => {
      const a = await approve(ex, taskId, sha, { requireHandoff: true });
      await resumeStep(ex.task(taskId).runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    },
    integrate: async (taskId) => {
      const t = ex.task(taskId);
      if (t.status !== 'approved') throw new Error(`승인된 상태가 아님(${t.status})`);
      await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
    },
    assign: async (input) => {
      const result = await prepareTask(input);
      if (input.start !== false) await startTask(result.taskId!);
    },
  });
}
