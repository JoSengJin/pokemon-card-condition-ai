import { getTask } from './executorLookup.ts';
import { record, type Resume } from './taskControlRecord.ts';
import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export async function withdrawApproval(ex: Executor, taskId: string, resume: Resume, rereview: (taskId: string) => Promise<unknown>) {
  const t = getTask(ex, taskId);
  if (!['approved', 'integration_blocked'].includes(t.status) || !t.approval) throw new UserError(`승인 취소는 승인됨 상태에서만 가능(${t.status})`);
  const sha = t.approval.sha, oldRun = t.runId;
  t.approval = null;
  t.status = 'integration_refused';
  t.statusReason = '사용자가 승인을 취소 — 같은 SHA로 검토 단계로 되돌리는 중';
  record(ex, t, 'approval_withdrawn', { sha, runId: oldRun, status: t.status });
  if (oldRun) {
    try { await resume(oldRun, 'integrate-gate', { action: 'withdraw' }); }
    catch (err) { record(ex, t, 'resume_error', { runId: oldRun, error: (err as Error).message }); }
  }
  await rereview(taskId);
  return getTask(ex, taskId);
}
