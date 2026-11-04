import { createWorkflowStateReader } from '@mastra/core/workflows';
import type { Task } from './executor/executor.ts';
import { getMastra } from './runtimeCore.ts';

export async function runInfo(runId: string | null | undefined) {
  if (!runId) return null;
  try {
    const state = await getMastra().getWorkflow('pairTaskWorkflow').getWorkflowRunById(runId);
    if (!state) return { runId, status: 'missing', suspendedStep: null, payload: null, result: null };
    const suspended = createWorkflowStateReader(state).getSuspendedStep();
    return { runId, status: state.status as string, suspendedStep: suspended?.stepId ?? null, payload: suspended?.suspendPayload ?? null, result: (state as any).result ?? null };
  } catch (err) {
    return { runId, status: 'error', suspendedStep: null, payload: null, result: null, error: (err as Error).message };
  }
}

export function discrepancy(task: Task, info: Awaited<ReturnType<typeof runInfo>>): string | null {
  if (!task.runId) return null;
  if (!info) return 'Mastra 실행 기록 없음';
  const step = info.status === 'suspended' ? info.suspendedStep : null;
  let expected = true;
  if (task.status === 'running' || task.status === 'collecting') expected = step === 'await-exit' || info.status === 'running';
  else if (['manual_working', 'cancelling', 'orphan_running', 'exit_observed'].includes(task.status)) expected = step === 'await-exit';
  else if (task.status === 'review_pending') expected = step === 'review-gate';
  else if (task.status === 'approved') expected = step === 'integrate-gate' || step === 'review-gate';
  else if (task.status === 'integrating') expected = info.status === 'running';
  else if ((info.status === 'running' || info.status === 'suspended') && task.status !== 'starting') expected = false;
  const observed = `${info.status}${info.suspendedStep ? `@${info.suspendedStep}` : ''}`;
  if (task.status === 'unknown') return `실행 결과 불명 — Mastra 기록은 '${observed}'`;
  return expected ? null : `실행기 '${task.status}' ↔ Mastra '${observed}'`;
}
