import { cancelRunning } from './processCancel.ts';
import { cancelManual } from './taskManual.ts';
import { finishVerification } from './verificationLifecycle.ts';
import type { Executor } from './executor.ts';

export async function cancel(taskExecutor: Executor, taskId: string): Promise<{ ok: boolean; reason: string }> {
  const t = taskExecutor.task(taskId);
  if (t.status === 'manual_working') return cancelManual(taskExecutor, taskId);
  if (t.verification?.status === 'running' && !t.verification.items.some((item) => item.status === 'running')) {
    finishVerification(taskExecutor, t, 'cancelled', '사용자 중단(검사 프로세스 시작 전)');
    return { ok: true, reason: '시작 전 작업 테스트 취소' };
  }
  return cancelRunning(taskExecutor, taskId);
}

export function cancelAll(taskExecutor: Executor, reason: string, agent?: string) {
  const busy = new Set(Object.values(taskExecutor.state.executions).filter((e) => ['running', 'cancelling'].includes(e.status) && (!agent || e.agent === agent)).map((e) => e.taskId));
  for (const t of Object.values(taskExecutor.state.tasks)) {
    if (busy.has(t.taskId)) void cancelRunning(taskExecutor, t.taskId).then((r) => taskExecutor.audit("cancel_all", { taskId: t.taskId, trigger: reason, result: r.reason, ok: r.ok }));
  }
}
