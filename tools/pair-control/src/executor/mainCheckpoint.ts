// 메인 교대용 체크포인트: 이전 메인의 대화 기억 없이도 새 메인이 이어받을 수 있게, 도구에 저장된 상태와 실제 Git 헤드에서 만든다.
// 마지막 인계문이 없어도(한도 소진 직후) 상태 파일과 Git만으로 다시 만들 수 있다. 추정값은 넣지 않는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { OCCUPYING, type Executor, type Task } from './executor.ts';

/** 키 순서와 무관한 JSON 문자열(같은 내용은 같은 해시). 직접 재귀하지 않고 JSON.stringify의 순회에 키 정렬만 얹는다. */
export const stable = (v: unknown): string => JSON.stringify(v, (_k, x) => (x && typeof x === 'object' && !Array.isArray(x) ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, x[k]])) : x)) ?? 'null';
export const hashOf = (v: unknown) => crypto.createHash('sha256').update(stable(v)).digest('hex');

/** 완료 여부를 모르는 상태. 확인 전에는 같은 행동을 다시 하지 않는다(재실행 금지 표시). */
const UNCERTAIN = ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'];

export async function liveHead(t: Task): Promise<string | null> {
  try { return (await G.revParse(t.worktree, `refs/heads/${t.branch}`)) ?? null; } catch { return null; }
}

function taskRow(ex: Executor, t: Task, head: string | null) {
  const r = t.result, h = t.handoff && !t.handoff.cancelledAt ? t.handoff : null;
  return {
    taskId: t.taskId, agent: t.agent, mode: t.mode, status: t.status, worktree: t.worktree, branch: t.branch, baseSha: t.baseSha, headSha: r?.headSha ?? null, liveHead: head,
    contractSha: t.contractSha, contractHash: t.contractHash, allowedFiles: t.allowedFiles, occupying: OCCUPYING.includes(t.status),
    turn: ex.turnOf(t).label, doNotRetry: UNCERTAIN.includes(t.status) || t.verification?.status === 'unknown',
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
  const tasks = Object.values(ex.state.tasks);
  const rows = [];
  for (const t of tasks) rows.push(taskRow(ex, t, await liveHead(t)));
  const running = Object.values(ex.state.executions).filter((e) => e.status === 'running' || e.status === 'cancelling');
  const pushes = Object.values(ex.state.pushes ?? {}).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 5)
    .map((p) => ({ id: p.id, status: p.status, preRemoteHead: p.preRemoteHead, pushedSha: p.pushedSha, doNotRetry: p.status === 'push_unverified' || p.status === 'remote_mismatch' }));
  const rt = ex.runtime;
  return {
    schema: 'main-checkpoint/v1', why, at: new Date().toISOString(), generation: rt.generation, from: ex.mainAgent, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    tasks: rows, nextActionCandidates: candidates(rows),
    inheritedExecutions: running.map((e) => ({ execId: e.execId, kind: e.kind ?? 'agent', taskId: e.taskId, pid: e.pid, note: '중단하지 않고 새 메인이 담당·결과를 인수' })),
    integrationLock: ex.locks.holder('integration') ?? null, pushes, approvals: rt.approvals.filter((a) => !a.revokedAt),
    limited: rt.limited, globalLimit: ex.limit,
    unverified: ['실제 CLI의 세션 재개·도구 동작', '이전 메인의 대화 기억(승계되지 않음)', ...rows.filter((r) => r.doNotRetry).map((r) => `${r.taskId}: 결과 불명(${r.status}) — 확인 전 재실행 금지`)],
  };
}

/** 체크포인트를 파일로 저장하고 내용 해시를 돌려준다. 해시는 파일 내용(해시 필드 제외) 기준이다. */
export async function saveCheckpoint(ex: Executor, why: string) {
  const data = await buildCheckpoint(ex, why);
  const hash = hashOf(data);
  const file = path.join(ex.cfg.stateDir, 'main-checkpoints', `${data.at.replace(/[:.]/g, '-')}-${why}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify({ ...data, contentHash: hash }, null, 2));
  ex.runtime.lastCheckpoint = file;
  ex.store.save();
  return { file, hash, data };
}
