import { prepHolds } from '../executor/approvalScope.ts';
import { registerApiRoute } from '@mastra/core/server';
import { grantApproval } from '../executor/mainApprovals.ts';
import { handoverBlockers, handoverMain } from '../executor/mainHandover.ts';
import { handoverAfterLimit } from '../executor/mainLimit.ts';
import { setMain, swapBlockers } from '../executor/mainRole.ts';
import { pipelineSummary } from '../executor/pipelineView.ts';
import { mainRuntimeView } from '../runtime.ts';
import { act, body } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const mainRoutes = [
  registerApiRoute('/pair/api/main/blockers', { method: 'GET', handler: act(async () => ({ blockers: await swapBlockers(executor) })) }),
  registerApiRoute('/pair/api/main/swap', { method: 'POST', handler: act(async (c) => { const b = await body(c); return setMain(executor, String(b.agent ?? ''), String(b.reason ?? '')); }) }),
  registerApiRoute('/pair/api/main/handover-blockers', { method: 'GET', handler: act(async () => ({ blockers: await handoverBlockers(executor) })) }),
  registerApiRoute('/pair/api/main/runtime', { method: 'GET', handler: act(async () => mainRuntimeView(executor, pipelineSummary(executor, prepHolds(executor, executor.runtime.session?.id)))) }),
  registerApiRoute('/pair/api/main/handover', { method: 'POST', handler: act(async (c) => { const b = await body(c), reason = String(b.reason ?? ''); return b.limit === true ? handoverAfterLimit(executor, String(b.agent ?? ''), [], reason) : handoverMain(executor, String(b.agent ?? ''), { reason }); }) }),
  registerApiRoute('/pair/api/main/approvals', { method: 'POST', handler: act(async (c) => { const b = await body(c); return grantApproval(executor, { basis: String(b.basis ?? ''), actions: Array.isArray(b.actions) ? b.actions.map(String) : [], targets: b.targets === '*' ? '*' : Array.isArray(b.targets) ? b.targets.map(String) : '*', conditions: String(b.conditions ?? ''), requires: b.requires as { handoffConfirmed?: boolean } | undefined }); }) }),
];
