import { diff } from '../executor/taskCollect.ts';
import { registerApiRoute } from '@mastra/core/server';
import { extractScope } from '../executor/scope.ts';
import { archiveFinished, discardTask, setArchived } from '../executor/taskControl.ts';
import { resumeStep, startReview } from '../runtime.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskAdminRoutes = [
  registerApiRoute('/pair/api/tasks/:id/archive', { method: 'POST', handler: act(async (c) => setArchived(executor, id(c), (await body(c)).archived !== false)) }),
  registerApiRoute('/pair/api/tasks/:id/discard', { method: 'POST', handler: act(async (c) => discardTask(executor, id(c), String((await body(c)).reason ?? ''), resumeStep)) }),
  registerApiRoute('/pair/api/archive-finished', { method: 'POST', handler: act(async () => archiveFinished(executor)) }),
  registerApiRoute('/pair/api/scope', { method: 'POST', handler: act(async (c) => extractScope(String((await body(c)).text ?? ''))) }),
  registerApiRoute('/pair/api/tasks/:id/rereview', { method: 'POST', handler: act(async (c) => startReview(id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/diff', { method: 'GET', handler: act(async (c) => ({ diff: await diff(executor, id(c)) })) }),
];
