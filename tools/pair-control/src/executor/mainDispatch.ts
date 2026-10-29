// 새 메인의 행동을 기존 기능(연결부 MainOps)으로 실제 수행한다. 승인 범위 검사는 mainActions가 이미 마쳤고, 여기서는 행동별 마지막 증거 검사만 한다.
// 확인(confirm_handoff)은 모델이 diff를 실제로 본 증거(현재 SHA·변경 파일 전체·도구가 계산한 diff 해시·메모)가 맞을 때만 받는다. 그래도 의미 검토 자체를 증명하지는 못한다.
import crypto from 'node:crypto';
import * as G from './git.ts';
import { verifyPushScope } from './pushOwnership.ts';
import { UserError, type Executor } from './executor.ts';
import type { Approval, MainAction, MainOps } from './mainTypes.ts';

/** 확인 행동의 증거를 현재 실제 상태와 대조한다. 어긋나면 UserError. */
async function confirmGate(ex: Executor, a: MainAction, taskId: string, selfReview: boolean) {
  const t = ex.state.tasks[taskId], h = t?.handoff, r = t?.result;
  if (!t || t.status !== 'review_pending' || !h || h.cancelledAt || h.confirmedAt) throw new UserError(`${taskId}: 확인할 수 있는 인계 상태가 아님`);
  const live = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
  if (!r?.headSha || a.sha !== r.headSha || h.headSha !== r.headSha || live !== r.headSha) throw new UserError(`${taskId}: 확인 SHA가 현재 결과·인계·Git과 다름`);
  if (!r.checksPassed || t.verification?.status !== 'passed' || t.verification.sha !== r.headSha) throw new UserError(`${taskId}: 계약 검사·작업 테스트가 현재 SHA에서 통과하지 않음`);
  if (t.agent === ex.mainAgent && !selfReview) throw new UserError(`${taskId}: 구현 에이전트(${t.agent})와 메인이 같아 독립 확인이 아님 — 사용자가 confirm_handoff 승인에 selfReview를 명시해야 함`);
  const seen = [...new Set(a.reviewedFiles ?? [])].sort().join('\n');
  if (!String(a.note ?? '').trim() || seen !== [...r.changedFiles].sort().join('\n')) throw new UserError(`${taskId}: 검토 메모가 없거나 검토한 파일 목록이 변경 파일 전체와 다름`);
  if (a.diffHash !== crypto.createHash('sha256').update((await G.git(t.worktree, 'diff', '--binary', t.baseSha, r.headSha)).stdout).digest('hex')) throw new UserError(`${taskId}: diff 해시가 도구 계산값과 다름 — 실제 diff를 읽은 증거 없음`);
}

/**
 * push: 점검·잠금·원격 재확인을 마친 같은 계획에 대해 실제 push 직전에 범위를 검사한다(verifyPushScope).
 * 범위의 모든 커밋이 통합 승인된 작업의 이력에 대응하지 않으면 자동 push를 하지 않는다. 일반 push(force 없음)만 한다.
 */
async function pushNow(ex: Executor, sessionId: string, a: MainAction, push: NonNullable<MainOps['push']>) {
  const sha = String(a.sha ?? '').toLowerCase();
  if (sha.length < 12) throw new UserError('push 확인 SHA는 앞 12자 이상이어야 함');
  const r = await push(sha, (plan) => verifyPushScope(ex, sessionId, plan));
  if (r.status !== 'pushed_verified') throw new UserError(`push가 검증되지 않음(${r.status}): ${r.detail}`);
}

export async function dispatch(ex: Executor, sessionId: string, a: MainAction, p: { target: string; input?: Record<string, unknown> }, ap: Approval): Promise<void> {
  const ops = ex.mainOps;
  if (a.type === 'approve_task' && ops.approve) await ops.approve(p.target, String(a.sha ?? ''));
  else if (a.type === 'integrate_task' && ops.integrate) await ops.integrate(p.target);
  else if (a.type === 'assign_task' && ops.assign) await ops.assign(p.input ?? {});
  else if (a.type === 'confirm_handoff' && ops.confirm) { await confirmGate(ex, a, p.target, !!ap.requires?.selfReview); await ops.confirm(p.target, `${ex.state.tasks[p.target].agent === ex.mainAgent ? '[자기 확인 — 독립 확인 아님] ' : ''}${String(a.note)}`.slice(0, 500)); }
  else if (a.type === 'push_main' && ops.push) await pushNow(ex, sessionId, a, ops.push);
  else throw new UserError(`지원하지 않거나 연결되지 않은 행동(${a.type}) — 수행하지 않음`);
}
