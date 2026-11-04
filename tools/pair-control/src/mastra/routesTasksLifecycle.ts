import { applyObservedExit } from '../executor/taskRecovery.ts';
import { registerApiRoute } from '@mastra/core/server';
import { planTask } from '../executor/prepare.ts';
import { pipelineView } from '../executor/pipelineView.ts';
import { prepareTask, snapshot, startTask } from '../runtime.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskLifecycleRoutes = [
  registerApiRoute('/pair/api/state', { method: 'GET', handler: act(async () => snapshot(pipelineView(executor))) }),
  registerApiRoute('/pair/api/tasks', { method: 'POST', handler: act(async (c) => prepareTask(await body(c))) }),
  registerApiRoute('/pair/api/plan', { method: 'POST', handler: act(async (c) => planTask(executor, await body(c))) }),
  registerApiRoute('/pair/api/tasks/:id/start', { method: 'POST', handler: act(async (c) => startTask(id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/cancel', { method: 'POST', handler: act(async (c) => executor.cancel(id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/apply-exit', { method: 'POST', handler: act(async (c) => applyObservedExit(executor, id(c))) }),
];
