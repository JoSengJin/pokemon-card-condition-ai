import { approve, reject } from '../executor/taskApproval.ts';
import { acknowledgeUnknown } from '../executor/taskRecovery.ts';
import { registerApiRoute } from '@mastra/core/server';
import { UserError } from '../executor/executor.ts';
import { resumeStep, startReview } from '../runtime.ts';
import { withdrawApproval } from '../executor/taskControl.ts';
import { act, body, id } from './apiBase.ts';
import { executor } from './serverContext.ts';

export const taskDecisionRoutes = [
  registerApiRoute('/pair/api/tasks/:id/ack-unknown', { method: 'POST', handler: act(async (c) => acknowledgeUnknown(executor, id(c))) }),
  registerApiRoute('/pair/api/tasks/:id/approve', { method: 'POST', handler: act(async (c) => {
    const task = executor.task(id(c)), { sha } = await body(c);
    const approval = await approve(executor, task.taskId, String(sha ?? ''), { requireHandoff: true });
    await resumeStep(task.runId!, 'review-gate', { decision: 'approve', sha: approval.sha });
    return approval;
  }) }),
  registerApiRoute('/pair/api/tasks/:id/reject', { method: 'POST', handler: act(async (c) => {
    const task = executor.task(id(c)), { reason } = await body(c), previous = task.status;
    const step = previous === 'approved' ? 'integrate-gate' : 'review-gate';
    reject(executor, task.taskId, String(reason ?? '사용자 거절'));
    if (task.runId && (previous === 'approved' || previous === 'review_pending')) await resumeStep(task.runId, step, step === 'review-gate' ? { decision: 'reject', reason } : { action: 'reject', reason });
    return executor.task(task.taskId);
  }) }),
  registerApiRoute('/pair/api/tasks/:id/integrate', { method: 'POST', handler: act(async (c) => {
    const task = executor.task(id(c));
    if (task.status !== 'approved') throw new UserError(`승인된 상태가 아님(${task.status})`);
    await resumeStep(task.runId!, 'integrate-gate', { action: 'integrate' });
    return executor.task(task.taskId);
  }) }),
  registerApiRoute('/pair/api/tasks/:id/unapprove', { method: 'POST', handler: act(async (c) => withdrawApproval(executor, id(c), resumeStep, startReview)) }),
];
