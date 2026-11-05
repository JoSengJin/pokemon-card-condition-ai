import { getTask } from './executorLookup.ts';
import { reject } from './taskApproval.ts';
import { record, type Resume } from './taskControlRecord.ts';
import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export const DISCARD_VIA_REJECT = ['review_pending', 'approved', 'integration_refused', 'integration_blocked'];

export const DISCARD_DIRECT = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export const DISCARDABLE = [...DISCARD_VIA_REJECT, ...DISCARD_DIRECT];

export async function discardTask(ex: Executor, taskId: string, reason: string, resume: Resume) {
  const t = getTask(ex, taskId);
  const why = String(reason ?? '').trim().slice(0, 300);
  if (why.length < 2) throw new UserError('폐기 사유를 적어 주세요(다른 사람이 이유를 알 수 있게 기록됩니다)');
  const prev = t.status;
  if (DISCARD_VIA_REJECT.includes(prev)) {
    const runId = t.runId, step = prev === 'approved' ? 'integrate-gate' : 'review-gate';
    reject(ex, taskId, `폐기: ${why}`);
    if (runId && (prev === 'approved' || prev === 'review_pending')) await resume(runId, step, step === 'review-gate' ? { decision: 'reject', reason: why } : { action: 'reject', reason: why });
  } else if (!DISCARD_DIRECT.includes(prev)) {
    throw new UserError(prev === 'integrated' || prev === 'integrated_check_failed'
      ? `이미 기준 브랜치에 통합됨(${prev}) — 폐기가 아니라 푸시 후 "보관"하거나, 되돌리려면 푸시 화면의 되돌림을 쓰세요`
      : `진행 중인 작업은 폐기할 수 없음(${prev}) — 먼저 중단하거나 결과를 확정하세요`);
  }
  const at = new Date().toISOString();
  t.discard = { at, reason: why };
  t.archivedAt = at;
  record(ex, t, 'task_discarded', { from: prev, reason: why });
  return getTask(ex, taskId);
}
