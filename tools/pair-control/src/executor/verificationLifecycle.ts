import { resolveCheck } from './checkCommand.ts';
import { spawnSupervised } from './processSupervisor.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import type { Executor, Execution, Task, Verification } from './executor.ts';

export async function startNextCheck(taskExecutor: Executor, t: Task): Promise<void> {
  const v = t.verification!;
  const item = v.items.find((i) => i.status === 'pending');
  if (!item) return finishVerification(taskExecutor, t);
  const spec = t.checks.find((c) => c.id === item.id)!;
  const r = resolveCheck(t.worktree, spec, { base: t.baseSha, contract: t.contractSha, head: v.sha });
  try {
    const ex = spawnSupervised(taskExecutor, t, { kind: 'check', runId: v.runId, cwd: r.cwd, command: r.command, args: r.args, env: sanitizedChildEnv(), display: r.display, checkId: item.id, sha: v.sha });
    item.status = 'running'; item.execId = ex.execId; item.logPath = ex.logPath; item.startedAt = ex.startedAt;
    taskExecutor.store.save();
  } catch (err) {
    item.status = 'failed'; item.endedAt = new Date().toISOString(); v.note = `시작 실패: ${(err as Error).message}`;
    taskExecutor.store.save();
  }
}

export function finishVerification(taskExecutor: Executor, t: Task, forced?: Verification["status"], note?: string): void {
  const v = t.verification!;
  for (const i of v.items) if (i.status === 'pending' || i.status === 'running') i.status = 'not_run';
  v.status = forced ?? (v.items.every((i) => i.status === 'passed') ? 'passed' : 'failed');
  if (note) v.note = note;
  v.endedAt = new Date().toISOString();
  for (const n of [`task:${t.taskId}`, `worktree:${t.worktree}`]) taskExecutor.locks.release(n, 'execId', v.runId);
  taskExecutor.audit('checks_finished', { taskId: t.taskId, runId: v.runId, status: v.status, sha: v.sha });
  taskExecutor.store.save();
}

export async function onAuxEnd(taskExecutor: Executor, ex: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
  const t = taskExecutor.state.tasks[ex.taskId];
  const v = t.verification;
  if (!v || v.runId !== ex.runId) { taskExecutor.store.save(); return; }
  const item = v.items.find((i) => i.execId === ex.execId);
  if (item) {
    item.status = r.unknown ? 'unknown' : r.cancelled ? 'cancelled' : r.code === 0 ? 'passed' : 'failed';
    item.exitCode = r.code; item.endedAt = new Date().toISOString();
  }
  if (r.unknown) return finishVerification(taskExecutor, t, 'unknown', '검사 프로세스가 종료 기록 없이 사라짐(결과 불명) — 다시 실행 필요');
  if (r.cancelled) return finishVerification(taskExecutor, t, 'cancelled', '사용자 중단');
  if (ex.observedAfterRestart) return finishVerification(taskExecutor, t, 'interrupted', '서버 재시작으로 검사 순서가 끊김 — 남은 검사는 실행하지 않음. 다시 실행 필요');
  taskExecutor.store.save();
}
