import { limitFor } from './executorPolicy.ts';
import { validateOrigin } from '../runtimeRequestPolicy.ts';
import type { RuntimeOrigin } from '../runtimeRequests.ts';
import { getTask } from './executorLookup.ts';
import { spawnExec } from './taskSpawn.ts';
import { reserve } from './taskReserve.ts';
import { preflightChecks } from './taskPreflight.ts';
import crypto from 'node:crypto';
import { mockPlan, probe, realPlan, realReadiness, type LaunchPlan } from './adapters.ts';
import { buildStartPrompt } from './startPrompt.ts';
import { setStatus, releaseExecLocks } from './taskState.ts';
import type { ConflictReason } from './contract.ts';
import { STARTABLE, type Executor, type Check } from './executor.ts';

export async function launch(taskExecutor: Executor, taskId: string, runId: string, origin?: RuntimeOrigin): Promise<{ ok: true; execId: string; pid: number } | { ok: true; manual: true; execId: null } | { ok: false; reason: string; conflicts?: ConflictReason[]; checks?: Check[] }> {
  const t = getTask(taskExecutor, taskId);
  const execId = crypto.randomUUID();
  const r = reserve(taskExecutor, t, execId);
  if (!r.ok) {
    const occupants = [...new Set((r.conflicts ?? []).map((c) => c.otherTask))].map((id) => `${id}[${taskExecutor.state.tasks[id]?.status ?? '?'}]`).join(', ');
    const reason = r.conflicts?.length ? `${r.reason}: ${r.conflicts.map((c) => `${c.otherTask}(${c.kind} ${c.detail})`).join(', ')} — 점유 작업 ${occupants}. 필요 없으면 그 작업을 열어 "폐기"하세요` : r.reason;
    taskExecutor.audit('start_refused', { taskId, reason });
    // 실행 중 작업의 중복 시작이면 상태를 건드리지 않고, 시작 가능한 작업이면 거절 사유만 남긴다.
    if (STARTABLE.includes(t.status)) { t.statusReason = `시작 거절: ${reason}`; t.updatedAt = new Date().toISOString(); taskExecutor.store.save(); }
    return { ...r, reason };
  }
  try {
    const checks = await preflightChecks(taskExecutor, t);
    validateOrigin(taskExecutor, origin);
    t.preflight = checks;
    const failed = checks.filter((c) => !c.ok);
    const failedDetail = failed.map((c) => `${c.name}(${c.detail})`).join(', ');
    if (t.mode === 'manual') {
      if (failed.length) {
        const reason = `사전 검사 실패: ${failedDetail}`;
        releaseExecLocks(taskExecutor, t, execId);
        setStatus(taskExecutor, t, 'blocked', reason);
        return { ok: false, reason, checks };
      }
      // 수동 모드: 프로세스를 띄우지 않는다. 같은 잠금과 충돌 검사로 파일 소유권만 유지한다.
      t.manual = { execId, runId, startedAt: new Date().toISOString() };
      t.runId = runId; t.runHistory = [...t.runHistory, runId]; t.lastExecId = null;
      t.result = null; t.approval = null; t.integration = null; t.verification = null; t.review = null; t.handoff = null;
      t.permission = '수동 모드: 도구는 에이전트를 실행하지 않음. 에이전트 세션이 worktree에서 작업하며, 허용 파일은 "작업 완료" 후 diff로만 검사(실행 중 쓰기를 막지 않음).';
      setStatus(taskExecutor, t, 'manual_working', '수동 작업 중 — 에이전트 세션에서 작업 후 "작업 완료"를 누르세요');
      taskExecutor.audit('manual_started', { taskId, runId });
      return { ok: true as const, manual: true as const, execId: null };
    }
    let plan: LaunchPlan | { refused: string };
    if (t.mode === 'mock') plan = mockPlan(t, taskExecutor.cfg);
    else {
      taskExecutor.probes[t.agent] = await probe(t.agent, taskExecutor.cfg);
      // 수동 경로와 같은 시작 프롬프트를 쓴다. 사용자가 자리에 없으므로 unattended(사람 정답 추정·재요청 금지)를 켠다.
      const start = await buildStartPrompt(t, taskExecutor.mainAgent, { unattended: true });
      plan = realPlan(t, taskExecutor.probes[t.agent]!, taskExecutor.cfg, start.text);
    }
    if (failed.length || 'refused' in plan) {
      const reason = failed.length ? `사전 검사 실패: ${failedDetail}` : (plan as { refused: string }).refused;
      releaseExecLocks(taskExecutor, t, execId);
      setStatus(taskExecutor, t, 'blocked', reason);
      return { ok: false, reason, checks };
    }
    // 사전 검사·CLI 탐색 대기 중 철회된 권한으로 프로세스를 시작하지 않는다.
    validateOrigin(taskExecutor, origin);
    if (taskExecutor.guardAlert) throw new Error(`무료 가드 발동 상태: ${taskExecutor.guardAlert.detail}`);
    if (t.mode === 'real') {
      const readiness = realReadiness(t.agent, taskExecutor.probes[t.agent], taskExecutor.cfg, { worktree: t.worktree, limit: limitFor(taskExecutor, t.agent) });
      if (!readiness.available) throw new Error(`실제 ${t.agent} 실행 차단: ${readiness.blockers.map((b) => b.message).join(', ')}`);
    }
    t.permission = plan.permission;
    return spawnExec(taskExecutor, t, runId, execId, plan);
  } catch (err) {
    releaseExecLocks(taskExecutor, t, execId);
    setStatus(taskExecutor, t, 'blocked', `시작 오류: ${(err as Error).message}`);
    return { ok: false, reason: (err as Error).message };
  }
}
