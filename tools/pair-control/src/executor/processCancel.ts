import { groupAlive, ownsLeader } from './processIdentity.ts';
import { setStatus } from './taskState.ts';
import type { Executor } from './executor.ts';

export async function cancelRunning(taskExecutor: Executor, taskId: string): Promise<{ ok: boolean; reason: string }> {
  const t = taskExecutor.task(taskId);
  const ex = Object.values(taskExecutor.state.executions).filter((e) => e.taskId === taskId && ['running', 'cancelling'].includes(e.status))
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
  if (!ex) return { ok: false, reason: '이 실행기가 시작한 실행 중 프로세스가 없음' };
  const leader = ownsLeader(taskExecutor, ex);
  if (leader === false) return { ok: false, reason: `PID ${ex.pid}가 이 실행기의 감독 프로세스가 아님(중단 거부)` };
  if (leader === null && !groupAlive(taskExecutor, ex.pgid)) return { ok: false, reason: '프로세스 그룹이 이미 없음' };
  ex.cancelRequested = true; ex.status = 'cancelling';
  if ((ex.kind ?? 'agent') === 'agent') setStatus(taskExecutor, t, 'cancelling', `SIGTERM → 프로세스 그룹 ${ex.pgid}`);
  else { taskExecutor.audit('aux_cancel', { taskId, kind: ex.kind, execId: ex.execId }); taskExecutor.store.save(); }
  try { process.kill(-ex.pgid, 'SIGTERM'); } catch { /* gone */ }
  setTimeout(() => { if (groupAlive(taskExecutor, ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } }, 3000).unref?.();
  return { ok: true, reason: `${ex.kind ?? 'agent'} 프로세스 그룹 ${ex.pgid}에 SIGTERM (3초 후 남으면 SIGKILL)` };
}
