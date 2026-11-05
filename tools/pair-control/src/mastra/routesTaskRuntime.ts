import { runChecks } from '../executor/verificationStart.ts';
import { startReviewJob } from '../executor/reviewStart.ts';
import { handoffToMain } from '../executor/handoffCreate.ts';
import { startPrompt } from '../executor/executorPrompt.ts';
import { readHandoff } from '../executor/handoffRecords.ts';
import { logTail } from '../executor/executorView.ts';
import { registerApiRoute } from '@mastra/core/server';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskRuntimeRoutes = [
  registerApiRoute('/pair/api/execs/:id/log', { method: 'GET', handler: act(async (c) => logTail(executor, id(c), Number(c.req.query('from') ?? 0))) }),
  registerApiRoute('/pair/api/tasks/:id/review', { method: 'POST', handler: act(async (c) => { const b = await body(c); return startReviewJob(executor, id(c), { reviewer: b.reviewer, mode: b.mode === 'real' ? 'real' : 'mock', mockScenario: b.mockScenario }); }) }),
  registerApiRoute('/pair/api/tasks/:id/run-checks', { method: 'POST', handler: act(async (c) => runChecks(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/start-prompt', { method: 'POST', handler: act(startPrompt, async (c: any) => { const b = await body(c); return [executor, id(c), { unattended: b.unattended === true, extraDocs: Array.isArray(b.extraDocs) ? b.extraDocs.map(String) : [] }]; }) }),
  registerApiRoute('/pair/api/tasks/:id/handoff', { method: 'POST', handler: act(async (c) => {
    const auto = (await body(c)).auto === true, taskId = id(c);
    const handoff = await handoffToMain(executor, taskId);
    if (auto) {
      try { await startReviewJob(executor, taskId, { reviewer: executor.mainAgent, mode: 'real', forHandoff: true }); handoff.autoNote = executor.mainAgent + ' 자동 확인 시작(별도 프로세스, read-only)'; }
      catch (error) { handoff.autoNote = '자동 확인 안 함: ' + (error as Error).message + ' — 안내문을 직접 전달하세요'; }
    }
    return handoff;
  }) }),
  registerApiRoute('/pair/api/tasks/:id/handoff-text', { method: 'GET', handler: act(async (c) => readHandoff(executor, id(c))) }),
];
