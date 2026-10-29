// 체크포인트 내용 구성: 저장된 작업 상태 + 실제 Git 헤드 + 진행 중 실행·푸시·승인·한도. 추정값은 넣지 않는다.
import * as G from './git.ts';
import { OCCUPYING, type Executor, type Task } from './executor.ts';

/** 완료 여부를 모르는 상태. 확인 전에는 같은 행동을 다시 하지 않는다(재실행 금지 표시). */
const UNCERTAIN = ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'];

function taskRow(t: Task, head: string | null, turn: string) {
  const r = t.result, h = t.handoff && !t.handoff.cancelledAt ? t.handoff : null;
  return {
    taskId: t.taskId, agent: t.agent, mode: t.mode, status: t.status, worktree: t.worktree, branch: t.branch, baseSha: t.baseSha, headSha: r?.headSha ?? null, liveHead: head,
    contractSha: t.contractSha, contractHash: t.contractHash, allowedFiles: t.allowedFiles, occupying: OCCUPYING.includes(t.status),
    turn, doNotRetry: UNCERTAIN.includes(t.status) || t.verification?.status === 'unknown',
    handoff: h ? { to: h.to, headSha: h.headSha, confirmed: !!h.confirmedAt, auto: !!h.auto } : null,
    review: t.review ? { status: t.review.status, verdict: t.review.verdict ?? null } : null,
    checksPassed: !!r?.checksPassed, testsPassed: t.verification?.status === 'passed' && t.verification.sha === r?.headSha,
  };
}

/** 지금 상태에서 새 메인이 고려할 수 있는 다음 행동 후보(기계적 조건만). 선택·판단은 새 메인과 승인 장부가 한다. */
function candidates(rows: ReturnType<typeof taskRow>[]) {
  const out: { type: string; taskId: string; sha?: string }[] = [];
  for (const r of rows) {
    if (r.doNotRetry) continue;
    if (r.status === 'review_pending' && r.checksPassed && r.testsPassed && r.handoff?.confirmed && r.handoff.headSha === r.headSha) out.push({ type: 'approve_task', taskId: r.taskId, sha: r.headSha! });
    if (r.status === 'approved') out.push({ type: 'integrate_task', taskId: r.taskId });
  }
  return out;
}

export async function buildCheckpoint(ex: Executor, why: string) {
  // 헤드는 revParse 한 번(git 래퍼 없이 직접 실행)으로 읽는다: launchTurn → saveCheckpoint → buildCheckpoint → revParse → run (4회)
  const rows = [], running = [], rt = ex.runtime, unverified = ['실제 CLI의 세션 재개·도구 동작', '이전 메인의 대화 기억(승계되지 않음)'];
  for (const t of Object.values(ex.state.tasks)) rows.push(taskRow(t, await G.revParse(t.worktree, `refs/heads/${t.branch}`), ex.turnOf(t).label));
  for (const e of Object.values(ex.state.executions)) {
    if (e.status === 'running' || e.status === 'cancelling') running.push({ execId: e.execId, kind: e.kind ?? 'agent', taskId: e.taskId, pid: e.pid, note: '중단하지 않고 새 메인이 담당·결과를 인수' });
  }
  for (const r of rows) if (r.doNotRetry) unverified.push(`${r.taskId}: 결과 불명(${r.status}) — 확인 전 재실행 금지`);
  const pushes = [];
  for (const p of Object.values(ex.state.pushes ?? {}).slice(-5).reverse()) pushes.push({ id: p.id, status: p.status, preRemoteHead: p.preRemoteHead, pushedSha: p.pushedSha, doNotRetry: p.status === 'push_unverified' || p.status === 'remote_mismatch' });
  return {
    schema: 'main-checkpoint/v1', why, at: new Date().toISOString(), generation: rt.generation, from: ex.mainAgent, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    tasks: rows, nextActionCandidates: candidates(rows), inheritedExecutions: running,
    integrationLock: ex.locks.holder('integration') ?? null, pushes, approvals: rt.approvals.filter((a) => !a.revokedAt),
    limited: rt.limited, globalLimit: ex.limit, unverified,
  };
}
