import { recheckEnv } from '../executor/taskEnvironment.ts';
import { registerApiRoute } from '@mastra/core/server';
import { progressDraft, progressItems } from '../executor/progress.ts';
import { activityOf } from '../executor/taskControl.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskInspectRoutes = [
  registerApiRoute('/pair/api/tasks/:id/activity', { method: 'GET', handler: act(async (c) => activityOf(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/recheck-env', { method: 'POST', handler: act(async (c) => recheckEnv(executor, id(c))) }),
  registerApiRoute('/pair/api/progress', { method: 'GET', handler: act(async () => progressItems(executor)) }),
  registerApiRoute('/pair/api/progress/draft', { method: 'POST', handler: act(async (c) => progressDraft(executor, String((await body(c)).id ?? ''))) }),
];
