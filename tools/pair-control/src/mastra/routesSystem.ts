import { refreshProbes } from '../executor/executorView.ts';
import { registerApiRoute } from '@mastra/core/server';
import { prepareRevert } from '../executor/push.ts';
import { act, body } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const systemRoutes = [
  registerApiRoute('/pair/api/push/revert-prepare', { method: 'POST', handler: act(async (c) => prepareRevert(executor, String((await body(c)).id ?? ''))) }),
  registerApiRoute('/pair/api/limit/clear', { method: 'POST', handler: act(async () => executor.clearLimit()) }),
  registerApiRoute('/pair/api/probes', { method: 'POST', handler: act(async () => refreshProbes(executor)) }),
];
