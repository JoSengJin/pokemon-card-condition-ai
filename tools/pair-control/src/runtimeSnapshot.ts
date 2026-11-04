import { groupAlive } from './executor/processIdentity.ts';
import { turnOf } from './executor/executorView.ts';
import { groupsOf } from './executor/executorView.ts';
import fs from 'node:fs';
import path from 'node:path';
import { realReadiness } from './executor/adapters.ts';
import type { Executor } from './executor/executor.ts';
import { pipelineView } from './executor/pipelineView.ts';
import { pushState } from './executor/push.ts';
import { getExecutor } from './runtimeCore.ts';
import { discrepancy, runInfo } from './runtimeInfo.ts';

export function mainRuntimeView(ex: Executor, pipeline: ReturnType<typeof pipelineView>) {
  const rt = ex.runtime, session = rt.session;
  return {
    generation: rt.generation, frozen: rt.frozen, limited: rt.limited, lastCheckpoint: rt.lastCheckpoint ?? null,
    session: session && { id: session.id, agent: session.agent, from: session.from, generation: session.generation, status: session.status, limitRecovery: session.limitRecovery, ackedAt: session.ackedAt ?? null, completedAt: session.completedAt ?? null, actionResults: session.actionResults },
    failures: rt.failures.slice(-3), pipeline,
    approvals: rt.approvals.map((a) => ({ id: a.id, basis: a.basis, actions: a.actions, targets: a.targets, conditions: a.conditions, requires: a.requires ?? null, boundSessionId: a.boundSessionId ?? null, revokedAt: a.revokedAt ?? null })),
  };
}

export async function snapshot(pipeline: ReturnType<typeof pipelineView>) {
  const ex = getExecutor();
  const tasks = await Promise.all(Object.values(ex.state.tasks).map(async (task) => {
    const info = await runInfo(task.runId);
    const execution = task.lastExecId ? ex.state.executions[task.lastExecId] : null;
    return { ...task, groups: groupsOf(task), mastra: info, mismatch: discrepancy(task, info), turn: turnOf(task), exec: execution && { ...execution, token: undefined, groupAlive: groupAlive(ex, execution.pgid) } };
  }));
  tasks.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return {
    now: new Date().toISOString(), lifetime: ex.lifetime, mode: ex.cfg.allowRealModelCalls ? 'real-allowed' : 'mock-only',
    guard: ex.guardAlert, limit: ex.limit, mainRuntime: mainRuntimeView(ex, pipeline), main: ex.state.main ?? { agent: 'codex', since: null, reason: '기본값' }, push: pushState(ex), probes: ex.probes, integration: ex.cfg.integration, connection: connection(ex), tasks,
  };
}

export function connection(ex: Executor) {
  const repo = ex.cfg.repo, demoRoot = path.join(ex.cfg.toolRoot, '.demo');
  const real = (value: string) => { try { return fs.realpathSync.native(value); } catch { return value; } };
  const kind = !repo ? 'unconfigured' : real(repo).startsWith(real(demoRoot) + path.sep) ? 'demo' : 'real';
  return {
    kind, repo, integrationBranch: ex.cfg.integration.branch, integrationCheckout: ex.cfg.integration.checkout,
    realRun: { codex: realReadiness('codex', ex.probes.codex, ex.cfg, { limit: ex.limitFor('codex') }), claude: realReadiness('claude', ex.probes.claude, ex.cfg, { limit: ex.limitFor('claude') }) },
    mockRun: { available: true, note: '모델 요청 없는 mock 프로세스. 실제 코드 품질을 검증하지 않음.' },
  };
}
