import { prepHolds } from '../executor/approvalScope.ts';
import { cancel } from '../executor/taskCancel.ts';
import { applyObservedExit } from '../executor/taskRecovery.ts';
import { registerApiRoute } from '@mastra/core/server';
import { planTask } from '../executor/prepare.ts';
import { pipelineSummary } from '../executor/pipelineView.ts';
import { prepareTask, snapshot, startTask } from '../runtime.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskLifecycleRoutes = [
  registerApiRoute('/pair/api/state', { method: 'GET', handler: act(snapshot, async () => [pipelineSummary(executor, prepHolds(executor, executor.runtime.session?.id))]) }),
  registerApiRoute('/pair/api/tasks', { method: 'POST', handler: act(async (c) => prepareTask(await body(c))) }),
  registerApiRoute('/pair/api/plan', { method: 'POST', handler: act(planTask, async (c: any) => [executor, await body(c)]) }),
  registerApiRoute('/pair/api/tasks/:id/start', { method: 'POST', handler: act(async (c) => startTask(id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/cancel', { method: 'POST', handler: act(cancel, async (c: any) => [executor, id(c)]) }),
  registerApiRoute('/pair/api/tasks/:id/apply-exit', { method: 'POST', handler: act(async (c) => applyObservedExit(executor, id(c))) }),
];
