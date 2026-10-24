// 실행기와 Mastra workflow를 잇는 단일 런타임. workflow 단계는 getExecutor()로 실행기를 호출한다.
import type { Mastra } from '@mastra/core/mastra';
import { createWorkflowStateReader } from '@mastra/core/workflows';
import { Executor, UserError, type Task } from './executor/executor.ts';

let executor: Executor | null = null;
let mastra: Mastra | null = null;

export function getExecutor(): Executor {
  if (!executor) throw new Error('pair-control 실행기가 초기화되지 않음');
  return executor;
}

export function bindRuntime(ex: Executor, m: Mastra) {
  executor = ex; mastra = m;
  ex.setResumer(async (runId, step, data) => { await resumeStep(runId, step, data); });
}

function wf() {
  if (!mastra) throw new Error('Mastra 인스턴스가 없음');
  return mastra.getWorkflow('pairTaskWorkflow');
}

export async function startTask(taskId: string) {
  const ex = getExecutor();
  ex.task(taskId);
  const run = await wf().createRun({ resourceId: taskId });
  const res = await run.start({ inputData: { taskId } });
  const outcome = res.status === 'success' ? (res.result as { outcome?: string; detail?: string } | undefined) : undefined;
  if (outcome?.outcome === 'blocked') throw new UserError(outcome.detail ?? '시작 차단');
  return { runId: run.runId, status: res.status, task: ex.task(taskId) };
}

/** 통합이 거절된 작업을 같은 브랜치 HEAD로 다시 검토(CLI 재실행 없음). */
export async function startReview(taskId: string) {
  const ex = getExecutor();
  const t = ex.task(taskId);
  if (t.status !== 'integration_refused') throw new UserError(`재검토는 통합 거절(승인 무효화) 상태에서만 가능(${t.status})`);
  const run = await wf().createRun({ resourceId: taskId });
  t.runId = run.runId; t.runHistory = [...t.runHistory, run.runId]; ex.store.save();
  const res = await run.start({ inputData: { taskId, reviewOnly: true } });
  return { runId: run.runId, status: res.status };
}

export async function resumeStep(runId: string, step: string, resumeData: Record<string, unknown>) {
  const run = await wf().createRun({ runId });
  const res = await run.resume({ step, resumeData });
  return res.status;
}

export async function runInfo(runId: string | null | undefined) {
  if (!runId) return null;
  try {
    const state = await wf().getWorkflowRunById(runId);
    if (!state) return { runId, status: 'missing', suspendedStep: null, payload: null, result: null };
    const reader = createWorkflowStateReader(state);
    const s = reader.getSuspendedStep();
    return { runId, status: state.status as string, suspendedStep: s?.stepId ?? null, payload: s?.suspendPayload ?? null, result: (state as any).result ?? null };
  } catch (err) {
    return { runId, status: 'error', suspendedStep: null, payload: null, result: null, error: (err as Error).message };
  }
}

/** 실행기 상태와 Mastra 실행 기록이 기대 관계를 벗어나면 그 차이를 문장으로 돌려준다. */
export function discrepancy(t: Task, info: Awaited<ReturnType<typeof runInfo>>): string | null {
  if (!t.runId) return null;
  if (!info) return 'Mastra 실행 기록 없음';
  const at = (step: string) => info.status === 'suspended' && info.suspendedStep === step;
  const expect: Record<string, () => boolean> = {
    running: () => at('await-exit') || info.status === 'running',
    collecting: () => at('await-exit') || info.status === 'running',
    cancelling: () => at('await-exit'),
    orphan_running: () => at('await-exit'),
    exit_observed: () => at('await-exit'),
    review_pending: () => at('review-gate'),
    approved: () => at('integrate-gate') || at('review-gate'),
    integrating: () => info.status === 'running',
  };
  if (t.status === 'unknown') return `실행 결과 불명 — Mastra 기록은 '${info.status}${info.suspendedStep ? `@${info.suspendedStep}` : ''}'`;
  const fn = expect[t.status];
  if (fn && !fn()) return `실행기 '${t.status}' ↔ Mastra '${info.status}${info.suspendedStep ? `@${info.suspendedStep}` : ''}'`;
  if (!fn && (info.status === 'running' || info.status === 'suspended') && !['starting'].includes(t.status)) {
    return `실행기 '${t.status}'(진행 없음) ↔ Mastra '${info.status}${info.suspendedStep ? `@${info.suspendedStep}` : ''}'`;
  }
  return null;
}

export async function snapshot() {
  const ex = getExecutor();
  const tasks = await Promise.all(Object.values(ex.state.tasks).map(async (t) => {
    const info = await runInfo(t.runId);
    const exec = t.lastExecId ? ex.state.executions[t.lastExecId] : null;
    return {
      ...t, groups: ex.groupsOf(t), mastra: info, mismatch: discrepancy(t, info),
      exec: exec && { ...exec, token: undefined, groupAlive: ex.groupAlive(exec.pgid) },
    };
  }));
  tasks.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return {
    now: new Date().toISOString(), lifetime: ex.lifetime, mode: ex.cfg.allowRealModelCalls ? 'real-allowed' : 'mock-only',
    guard: ex.guardAlert, probes: ex.probes, integration: ex.cfg.integration, tasks,
  };
}
