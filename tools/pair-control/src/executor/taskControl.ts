// 작업 되돌리기 제어: 승인 취소(승인됨 → 검토 단계)와 작업 보관(목록에서 숨기기). 에이전트를 다시 실행하지 않는다.
import { appendEvent } from './store.ts';
import { OCCUPYING, UserError, type Executor, type Task } from './executor.ts';

type Resume = (runId: string, step: string, data: Record<string, unknown>) => Promise<unknown>;

function record(ex: Executor, t: Task, type: string, data: Record<string, unknown> = {}) {
  t.updatedAt = new Date().toISOString();
  appendEvent(ex.cfg.stateDir, { type, lifetime: ex.lifetime, taskId: t.taskId, ...data });
  ex.store.save();
}

/**
 * 승인을 취소하고 같은 SHA로 검토 단계로 되돌린다. 통합 전이라 통합 브랜치는 바뀌지 않는다.
 * 기존 workflow 실행은 integrate-gate에서 withdraw로 끝내고, 재검토(reviewOnly) 실행으로 결과를 다시 수집한다.
 * 같은 SHA·계약의 작업 테스트·리뷰·인계 기록은 그대로 유효하다.
 */
export async function withdrawApproval(ex: Executor, taskId: string, resume: Resume, rereview: (taskId: string) => Promise<unknown>) {
  const t = ex.task(taskId);
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
  return ex.task(taskId);
}

/** 끝났거나 시작 전인 작업만 목록에서 숨긴다. 기록·worktree·브랜치는 그대로 두고 언제든 해제할 수 있다. */
export function setArchived(ex: Executor, taskId: string, archived: boolean) {
  const t = ex.task(taskId);
  if (archived && OCCUPYING.includes(t.status)) throw new UserError(`진행 중이거나 결정이 남은 작업은 보관할 수 없음(${t.status}) — 먼저 취소·거절하거나 통합하세요`);
  t.archivedAt = archived ? new Date().toISOString() : null;
  record(ex, t, archived ? 'task_archived' : 'task_unarchived');
  return t;
}
