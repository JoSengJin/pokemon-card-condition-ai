import { handoffToMain, handoffToMainAuto } from '../executor/handoffCreate.ts';
import { startPrompt } from '../executor/executorPrompt.ts';
import { readHandoff } from '../executor/handoffRecords.ts';
import { logTail } from '../executor/executorView.ts';
import { registerApiRoute } from '@mastra/core/server';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskRuntimeRoutes = [
  registerApiRoute('/pair/api/execs/:id/log', { method: 'GET', handler: act(async (c) => logTail(executor, id(c), Number(c.req.query('from') ?? 0))) }),
  registerApiRoute('/pair/api/tasks/:id/review', { method: 'POST', handler: act(async (c) => { const b = await body(c); return executor.startReviewJob(id(c), { reviewer: b.reviewer, mode: b.mode === 'real' ? 'real' : 'mock', mockScenario: b.mockScenario }); }) }),
  registerApiRoute('/pair/api/tasks/:id/run-checks', { method: 'POST', handler: act(async (c) => executor.runChecks(id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/start-prompt', { method: 'POST', handler: act(async (c) => { const b = await body(c); return startPrompt(executor, id(c), { unattended: b.unattended === true, extraDocs: Array.isArray(b.extraDocs) ? b.extraDocs.map(String) : [] }); }) }),
  registerApiRoute('/pair/api/tasks/:id/handoff', { method: 'POST', handler: act(async (c) => (await body(c)).auto === true ? handoffToMainAuto(executor, id(c)) : handoffToMain(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/handoff-text', { method: 'GET', handler: act(async (c) => readHandoff(executor, id(c))) }),
];
