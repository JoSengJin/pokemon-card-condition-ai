import { UserError } from './executor/executor.ts';
import { getExecutor, getMastra } from './runtimeCore.ts';

export async function startTask(taskId: string) {
  const ex = getExecutor();
  ex.task(taskId);
  const run = await getMastra().getWorkflow('pairTaskWorkflow').createRun({ resourceId: taskId });
  const res = await run.start({ inputData: { taskId } });
  const outcome = res.status === 'success' ? (res.result as { outcome?: string; detail?: string } | undefined) : undefined;
  if (outcome?.outcome === 'blocked') throw new UserError(outcome.detail ?? '시작 차단');
  return { runId: run.runId, status: res.status, task: ex.task(taskId) };
}

export async function startReview(taskId: string) {
  const ex = getExecutor(), task = ex.task(taskId);
  if (task.status !== 'integration_refused') throw new UserError(`재검토는 통합 거절(승인 무효화) 상태에서만 가능(${task.status})`);
  const run = await getMastra().getWorkflow('pairTaskWorkflow').createRun({ resourceId: taskId });
  task.runId = run.runId; task.runHistory = [...task.runHistory, run.runId]; ex.store.save();
  const result = await run.start({ inputData: { taskId, reviewOnly: true } });
  return { runId: run.runId, status: result.status };
}

export async function prepareTask(input: unknown) {
  const run = await getMastra().getWorkflow('prepareTaskWorkflow').createRun();
  const result = await run.start({ inputData: input });
  const out = result.status === 'success' ? (result.result as { ok: boolean; taskId?: string; detail?: string }) : null;
  if (!out) throw new Error(`prepare-task 실패: ${result.status}`);
  if (!out.ok) throw new UserError(out.detail ?? '준비 실패');
  return { runId: run.runId, ...out, task: getExecutor().task(out.taskId!) };
}

export async function resumeStep(runId: string, step: string, resumeData: Record<string, unknown>) {
  const run = await getMastra().getWorkflow('pairTaskWorkflow').createRun({ runId });
  return (await run.resume({ step, resumeData })).status;
}
