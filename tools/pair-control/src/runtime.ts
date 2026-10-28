// 실행기와 Mastra workflow를 잇는 단일 런타임. workflow 단계는 getExecutor()로 실행기를 호출한다.
import type { Mastra } from '@mastra/core/mastra';
import { createWorkflowStateReader } from '@mastra/core/workflows';
import fs from 'node:fs';
import path from 'node:path';
import { Executor, UserError, type Task } from './executor/executor.ts';
import { realReadiness } from './executor/adapters.ts';
import { pushState } from './executor/push.ts';

let executor: Executor | null = null;
let mastra: Mastra | null = null;

export function getExecutor(): Executor {
  if (!executor) throw new Error('pair-control 실행기가 초기화되지 않음');
  return executor;
}

export function bindRuntime(ex: Executor, m: Mastra) {
  executor = ex; mastra = m;
  ex.setResumer(async (runId, step, data) => { await resumeStep(runId, step, data); });
  // 새 메인의 행동은 화면 버튼과 같은 기존 기능으로만 수행한다(새 권한 없음). 승인 장부 검사는 mainActions가 먼저 한다.
  ex.setMainOps({
    approve: async (taskId, sha) => {
      const a = await ex.approve(taskId, sha, { requireHandoff: true });
      await resumeStep(ex.task(taskId).runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    },
    integrate: async (taskId) => {
      const t = ex.task(taskId);
      if (t.status !== 'approved') throw new Error(`승인된 상태가 아님(${t.status})`);
      await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
    },
    assign: async (input) => { await prepareTask(input); },
  });
}

/** 화면용 메인 교대 상태 요약(토큰·해시 원문은 넣지 않는다). */
export function mainRuntimeView(ex: Executor) {
  const rt = ex.runtime, s = rt.session;
  return {
    generation: rt.generation, frozen: rt.frozen, limited: rt.limited, lastCheckpoint: rt.lastCheckpoint ?? null,
    session: s && { id: s.id, agent: s.agent, from: s.from, generation: s.generation, status: s.status, limitRecovery: s.limitRecovery, ackedAt: s.ackedAt ?? null, completedAt: s.completedAt ?? null, actionResults: s.actionResults },
    failures: rt.failures.slice(-3),
    approvals: rt.approvals.map((a) => ({ id: a.id, basis: a.basis, actions: a.actions, targets: a.targets, conditions: a.conditions, boundSessionId: a.boundSessionId ?? null, revokedAt: a.revokedAt ?? null })),
  };
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

/** 작업 준비 workflow 실행. 실패하면 사유를 UserError로 돌려준다. */
export async function prepareTask(input: unknown) {
  if (!mastra) throw new Error('Mastra 인스턴스가 없음');
  const run = await mastra.getWorkflow('prepareTaskWorkflow').createRun();
  const res = await run.start({ inputData: input });
  const out = res.status === 'success' ? (res.result as { ok: boolean; taskId?: string; detail?: string }) : null;
  if (!out) throw new Error(`prepare-task 실패: ${res.status}`);
  if (!out.ok) throw new UserError(out.detail ?? '준비 실패');
  return { runId: run.runId, ...out, task: getExecutor().task(out.taskId!) };
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
    manual_working: () => at('await-exit'),
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
      ...t, groups: ex.groupsOf(t), mastra: info, mismatch: discrepancy(t, info), turn: ex.turnOf(t),
      exec: exec && { ...exec, token: undefined, groupAlive: ex.groupAlive(exec.pgid) },
    };
  }));
  tasks.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return {
    now: new Date().toISOString(), lifetime: ex.lifetime, mode: ex.cfg.allowRealModelCalls ? 'real-allowed' : 'mock-only',
    guard: ex.guardAlert, limit: ex.limit, mainRuntime: mainRuntimeView(ex), main: ex.state.main ?? { agent: 'codex', since: null, reason: '기본값' }, push: pushState(ex), probes: ex.probes, integration: ex.cfg.integration, connection: connection(ex), tasks,
  };
}

/** 화면 상단 연결 상태: 어느 저장소에 연결됐는지와 실제 실행 가능 여부·차단 원인. */
export function connection(ex: Executor) {
  const repo = ex.cfg.repo;
  const demoRoot = path.join(ex.cfg.toolRoot, '.demo');
  const real = (p: string) => { try { return fs.realpathSync.native(p); } catch { return p; } };
  const kind = !repo ? 'unconfigured' : real(repo).startsWith(real(demoRoot) + path.sep) ? 'demo' : 'real';
  return {
    kind, repo, integrationBranch: ex.cfg.integration.branch, integrationCheckout: ex.cfg.integration.checkout,
    realRun: { codex: realReadiness('codex', ex.probes.codex, ex.cfg, { limit: ex.limit }), claude: realReadiness('claude', ex.probes.claude, ex.cfg, { limit: ex.limit }) },
    mockRun: { available: true, note: '모델 요청 없는 mock 프로세스. 실제 코드 품질을 검증하지 않음.' },
  };
}
