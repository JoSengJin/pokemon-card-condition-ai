import { conflicts, type ConflictReason } from './contract.ts';
import { setStatus } from './taskState.ts';
import { OCCUPYING, STARTABLE, type Executor, type Task } from './executor.ts';

export function reserve(taskExecutor: Executor, t: Task, execId: string): { ok: true } | { ok: false; reason: string; conflicts?: ConflictReason[] } {
  if (taskExecutor.guardAlert) return { ok: false, reason: `무료 가드 발동 상태: ${taskExecutor.guardAlert.detail}` };
  if (!STARTABLE.includes(t.status)) return { ok: false, reason: `현재 상태(${t.status})에서는 시작할 수 없음(중복 실행 차단)` };
  const found: ConflictReason[] = [];
  for (const o of Object.values(taskExecutor.state.tasks)) {
    if (o.taskId === t.taskId || !OCCUPYING.includes(o.status)) continue;
    found.push(...conflicts(t, o));
  }
  if (found.length) return { ok: false, reason: '다른 진행 중 작업과 충돌', conflicts: found };
  const names = [`task:${t.taskId}`, `worktree:${t.worktree}`, `branch:${t.branch}`];
  const got: string[] = [];
  for (const n of names) {
    if (!taskExecutor.locks.acquire(n, { execId, taskId: t.taskId, lifetime: taskExecutor.lifetime })) {
      for (const g of got) taskExecutor.locks.release(g, 'execId', execId);
      return { ok: false, reason: `잠금 사용 중: ${n} (소유 ${JSON.stringify(taskExecutor.locks.holder(n))})` };
    }
    got.push(n);
  }
  setStatus(taskExecutor, t, 'starting');
  return { ok: true };
}
