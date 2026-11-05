import { limitOf } from './executorLookup.ts';
import { turnOf } from './executorView.ts';
// 체크포인트 내용 구성: 저장된 작업 상태 + 실제 Git 헤드 + 진행 중 실행·푸시·승인·한도. 추정값은 넣지 않는다.
import { execFileSync } from 'node:child_process';
import { FULL_SHA } from './git.ts';
import { OCCUPYING, type Executor } from './executor.ts';

/** 완료 여부를 모르는 상태. 확인 전에는 같은 행동을 다시 하지 않는다(재실행 금지 표시). */
const UNCERTAIN = ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'];

export async function buildCheckpoint(ex: Executor, why: string) {
  // 체크포인트 구성 서비스가 Git 원시 결과를 직접 검증해 상위 교대 경로의 프레임 예산을 지킨다.
  const rows = [], running = [], rt = ex.runtime, unverified = ['실제 CLI의 세션 재개·도구 동작', '이전 메인의 대화 기억(승계되지 않음)'];
  for (const t of Object.values(ex.state.tasks)) {
    let sha: string | null = null;
    try { const value = execFileSync('git', ['rev-parse', '--verify', '--quiet', `refs/heads/${t.branch}^{commit}`], { cwd: t.worktree, encoding: 'utf8' }).trim(); sha = FULL_SHA.test(value) ? value : null; } catch { /* branch missing */ }
    const result = t.result, handoff = t.handoff && !t.handoff.cancelledAt ? t.handoff : null;
    rows.push({
      taskId: t.taskId, agent: t.agent, mode: t.mode, status: t.status, worktree: t.worktree, branch: t.branch, baseSha: t.baseSha, headSha: result?.headSha ?? null, liveHead: sha,
      contractSha: t.contractSha, contractHash: t.contractHash, allowedFiles: t.allowedFiles, occupying: OCCUPYING.includes(t.status), turn: turnOf(t).label,
      doNotRetry: UNCERTAIN.includes(t.status) || t.verification?.status === 'unknown',
      handoff: handoff ? { to: handoff.to, headSha: handoff.headSha, confirmed: !!handoff.confirmedAt, auto: !!handoff.auto } : null,
      review: t.review ? { status: t.review.status, verdict: t.review.verdict ?? null } : null,
      checksPassed: !!result?.checksPassed, testsPassed: t.verification?.status === 'passed' && t.verification.sha === result?.headSha,
    });
  }
  for (const e of Object.values(ex.state.executions)) {
    if (e.status === 'running' || e.status === 'cancelling') running.push({ execId: e.execId, kind: e.kind ?? 'agent', taskId: e.taskId, pid: e.pid, note: '중단하지 않고 새 메인이 담당·결과를 인수' });
  }
  for (const r of rows) if (r.doNotRetry) unverified.push(`${r.taskId}: 결과 불명(${r.status}) — 확인 전 재실행 금지`);
  const pushes = [];
  for (const p of Object.values(ex.state.pushes ?? {}).slice(-5).reverse()) pushes.push({ id: p.id, status: p.status, preRemoteHead: p.preRemoteHead, pushedSha: p.pushedSha, doNotRetry: p.status === 'push_unverified' || p.status === 'remote_mismatch' });
  const nextActionCandidates: { type: string; taskId: string; sha?: string }[] = [];
  for (const row of rows) {
    if (row.doNotRetry) continue;
    if (row.status === 'review_pending' && row.checksPassed && row.testsPassed && row.handoff?.confirmed && row.handoff.headSha === row.headSha) nextActionCandidates.push({ type: 'approve_task', taskId: row.taskId, sha: row.headSha! });
    if (row.status === 'approved') nextActionCandidates.push({ type: 'integrate_task', taskId: row.taskId });
  }
  return {
    schema: 'main-checkpoint/v1', why, at: new Date().toISOString(), generation: rt.generation, from: ex.mainAgent, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    tasks: rows, nextActionCandidates, inheritedExecutions: running,
    integrationLock: ex.locks.holder('integration') ?? null, pushes, approvals: rt.approvals.filter((a) => !a.revokedAt),
    limited: rt.limited, globalLimit: limitOf(ex), unverified,
  };
}
