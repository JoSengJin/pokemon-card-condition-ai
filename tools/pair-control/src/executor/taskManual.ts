import { UserError } from './errors.ts';
import { setStatus, releaseExecLocks } from './taskState.ts';
import type { Executor } from './executor.ts';

export async function finishManual(owner: Executor, taskId: string) {
  const t = owner.task(taskId);
  if (t.status !== 'manual_working' || !t.manual) throw new UserError(`수동 작업 중이 아님(${t.status})`);
  if (!owner.resumer || !t.runId) throw new UserError('workflow 연결 없음');
  releaseExecLocks(owner, t, t.manual.execId);
  t.manual.endedAt = new Date().toISOString(); t.manual.ended = 'finished';
  setStatus(owner, t, 'collecting', '사용자가 작업 완료를 표시 · 결과 수집 중');
  await owner.resumer(t.runId, 'await-exit', { execId: 'manual', exitCode: 0, signal: null, cancelled: false });
  return owner.task(taskId);
}

export async function cancelManual(owner: Executor, taskId: string): Promise<{ ok: boolean; reason: string }> {
  const t = owner.task(taskId);
  if (t.status !== 'manual_working' || !t.manual) return { ok: false, reason: '수동 작업 중이 아님' };
  releaseExecLocks(owner, t, t.manual.execId);
  t.manual.endedAt = new Date().toISOString(); t.manual.ended = 'cancelled';
  setStatus(owner, t, 'cancelled', '사용자가 수동 작업을 취소(에이전트 세션에서 진행한 변경은 worktree에 그대로 남음)');
  if (owner.resumer && t.runId) {
    try { await owner.resumer(t.runId, 'await-exit', { execId: 'manual', exitCode: null, signal: null, cancelled: true }); }
    catch (err) { owner.audit('resume_error', { taskId, error: (err as Error).message }); }
  }
  return { ok: true, reason: '수동 작업 취소 · 소유권 잠금 해제' };
}
