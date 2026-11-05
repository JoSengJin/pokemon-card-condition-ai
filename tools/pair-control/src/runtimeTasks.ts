import { getTask } from './executor/executorLookup.ts';
import { UserError } from './executor/executor.ts';
import { getExecutor } from './runtimeCore.ts';
import { startWorkflow, type RuntimeOrigin } from './runtimeRequests.ts';
export { resumeStep } from './runtimeRequests.ts';

export async function startTask(taskId: string, origin?: RuntimeOrigin) {
  const ex = getExecutor();
  getTask(ex, taskId);
  const res = await startWorkflow('pairTaskWorkflow', { taskId }, taskId, origin);
  const outcome = res.status === 'success' ? (res.result as { outcome?: string; detail?: string } | undefined) : undefined;
  if (outcome?.outcome === 'blocked') throw new UserError(outcome.detail ?? '시작 차단');
  return { runId: res.runId, status: res.status, task: getTask(ex, taskId) };
}

export async function startReview(taskId: string) {
  const ex = getExecutor(), task = getTask(ex, taskId);
  if (task.status !== 'integration_refused') throw new UserError(`재검토는 통합 거절(승인 무효화) 상태에서만 가능(${task.status})`);
  const result = await startWorkflow('pairTaskWorkflow', { taskId, reviewOnly: true }, taskId);
  task.runId = result.runId; task.runHistory = [...task.runHistory, result.runId]; ex.store.save();
  return { runId: result.runId, status: result.status };
}

export async function prepareTask(input: unknown, origin?: RuntimeOrigin) {
  const result = await startWorkflow('prepareTaskWorkflow', input, undefined, origin);
  const out = result.status === 'success' ? (result.result as { ok: boolean; taskId?: string; detail?: string }) : null;
  if (!out) throw new Error(`prepare-task 실패: ${result.status}`);
  if (!out.ok) throw new UserError(out.detail ?? '준비 실패');
  return { runId: result.runId, ...out, task: getTask(getExecutor(), out.taskId!) };
}
