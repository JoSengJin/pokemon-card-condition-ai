import { makeVenv } from '../executor/taskVenv.ts';
import { preflightChecks } from '../executor/taskPreflight.ts';
import { recollect } from '../executor/taskCollect.ts';
import { finishManual } from '../executor/taskManual.ts';
import { confirmHandoff, cancelHandoff } from '../executor/handoffRecords.ts';
import { registerApiRoute } from '@mastra/core/server';
import { tailPostLog } from '../executor/taskControl.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskFinishRoutes = [
  registerApiRoute('/pair/api/tasks/:id/handoff-confirm', { method: 'POST', handler: act(async (c) => confirmHandoff(executor, id(c), String((await body(c)).note ?? ''))) }),
  registerApiRoute('/pair/api/tasks/:id/handoff-cancel', { method: 'POST', handler: act(async (c) => cancelHandoff(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/finish-manual', { method: 'POST', handler: act(async (c) => finishManual(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/recollect', { method: 'POST', handler: act(recollect, async (c: any) => [executor, id(c)]) }),
  registerApiRoute('/pair/api/tasks/:id/create-venv', { method: 'POST', handler: act(async (c) => { const task = await makeVenv(executor, id(c)); task.preflight = await preflightChecks(executor, task); executor.store.save(); return task.envReadiness; }) }),
  registerApiRoute('/pair/api/tasks/:id/post-log', { method: 'GET', handler: act(async (c) => tailPostLog(executor, id(c), String(c.req.query('check') ?? ''), Number(c.req.query('from') ?? 0))) }),
];
