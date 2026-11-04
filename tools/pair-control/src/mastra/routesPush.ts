import { registerApiRoute } from '@mastra/core/server';
import { revokeApproval } from '../executor/mainApprovals.ts';
import { clearAgentLimit } from '../executor/mainHandover.ts';
import { acknowledgeFindings, preflight, runPush, verifyPush } from '../executor/push.ts';
import { pipelineView } from '../executor/pipelineView.ts';
import { mainRuntimeView } from '../runtime.ts';
import { act, body } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const pushRoutes = [
  registerApiRoute('/pair/api/main/approvals/revoke', { method: 'POST', handler: act(async (c) => revokeApproval(executor, String((await body(c)).id ?? ''))) }),
  registerApiRoute('/pair/api/main/limit-clear', { method: 'POST', handler: act(async (c) => { clearAgentLimit(executor, String((await body(c)).agent ?? '') as 'codex'); return mainRuntimeView(executor, pipelineView(executor)); }) }),
  registerApiRoute('/pair/api/push/preflight', { method: 'POST', handler: act(async () => preflight(executor)) }),
  registerApiRoute('/pair/api/push/ack', { method: 'POST', handler: act(async (c) => { const b = await body(c); return acknowledgeFindings(executor, Array.isArray(b.fingerprints) ? b.fingerprints.map(String) : []); }) }),
  registerApiRoute('/pair/api/push/run', { method: 'POST', handler: act(async (c) => runPush(executor, String((await body(c)).confirm ?? ''))) }),
  registerApiRoute('/pair/api/push/verify', { method: 'POST', handler: act(async (c) => verifyPush(executor, String((await body(c)).id ?? ''))) }),
];
