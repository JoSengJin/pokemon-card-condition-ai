import crypto from 'node:crypto';
import * as G from './git.ts';
import { appendEvent } from './store.ts';
import { setStatus } from './taskState.ts';
import { UserError } from './errors.ts';
import type { Executor, Approval } from './executor.ts';

export async function approve(taskExecutor: Executor, taskId: string, sha: string, o: { requireHandoff?: boolean } = {}): Promise<Approval> {
  taskExecutor.assertMainActive('승인');
  const t = taskExecutor.task(taskId);
  if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태가 아님(${t.status})`);
  if (o.requireHandoff) {
    if (t.review?.status === 'running') throw new UserError('리뷰가 실행 중 — 끝난 뒤 승인할 수 있음');
    const h = t.handoff;
    if (!h || h.cancelledAt) throw new UserError('메인 인계가 끝나지 않음 — 인계하고 확인 완료를 받은 뒤 승인할 수 있음');
    if (h.headSha !== t.result?.headSha) throw new UserError('인계 후 코드가 바뀜 — 다시 인계하고 확인을 받으세요');
    if (!h.confirmedAt) throw new UserError('메인 확인이 끝나지 않음 — 확인 완료 후 승인할 수 있음');
  }
  if (!G.FULL_SHA.test(sha)) throw new UserError('전체 40자 SHA로 승인해야 함');
  if (!t.result?.checksPassed) throw new UserError('Git 계약 검사 실패가 있어 승인할 수 없음');
  const v = t.verification;
  if (!v || v.status !== 'passed') throw new UserError(`작업 테스트가 통과하지 않음(${v ? v.status : '미실행'}) — 미실행·실패·중단·결과 불명은 통과가 아님`);
  if (v.sha !== sha || v.contractHash !== t.contractHash) throw new UserError('작업 테스트 결과가 현재 SHA·계약과 다름 — 다시 실행');
  const headResult = await G.run('git', ['rev-parse', '--verify', '--quiet', `refs/heads/${t.branch}^{commit}`], t.worktree);
  const head = headResult.code === 0 && G.FULL_SHA.test(headResult.stdout.trim()) ? headResult.stdout.trim() : null;
  if (head !== sha || t.result.headSha !== sha) throw new UserError(`승인 SHA가 현재 결과와 다름(현재 ${head})`);
  if (!taskExecutor.cfg.integration.checkout) throw new UserError('config.integration.checkout 미설정');
  const changed = await G.run('git', ['diff', '--name-only', '-z', `${t.baseSha}..${sha}`], t.worktree);
  const files = changed.stdout.split('\0').filter(Boolean).sort();
  const base = await G.run('git', ['rev-parse', '--verify', '--quiet', `refs/heads/${taskExecutor.cfg.integration.branch}^{commit}`], taskExecutor.cfg.integration.checkout);
  const baseHead = G.FULL_SHA.test(base.stdout.trim()) ? base.stdout.trim() : null;
  if (!baseHead) throw new UserError('통합 기준 브랜치를 읽지 못함');
  const filesHash = crypto.createHash('sha256').update(files.join('\0')).digest('hex');
  const rv = t.review && t.review.sha === sha && t.review.contractHash === t.contractHash && t.review.status === 'done' ? t.review.verdict ?? null : null;
  const ho = t.handoff && !t.handoff.cancelledAt && t.handoff.headSha === sha ? t.handoff.confirmedAt ?? null : null;
  t.approval = { sha, baseBranch: taskExecutor.cfg.integration.branch, baseHead, files, filesHash, contractHash: t.contractHash, reviewVerdict: rv, mainConfirmedAt: ho, at: new Date().toISOString() };
  t.status = 'approved'; t.statusReason = `SHA ${sha.slice(0, 12)} 승인 · 통합 실행 대기`; t.updatedAt = new Date().toISOString();
  appendEvent(taskExecutor.cfg.stateDir, { type: 'task_status', lifetime: taskExecutor.lifetime, taskId: t.taskId, status: t.status, reason: t.statusReason });
  taskExecutor.store.save();
  appendEvent(taskExecutor.cfg.stateDir, { type: 'approved', lifetime: taskExecutor.lifetime, taskId, sha, baseHead });
  return t.approval;
}

export function reject(taskExecutor: Executor, taskId: string, reason: string) {
  taskExecutor.assertMainActive('거절');
  const t = taskExecutor.task(taskId);
  if (!['review_pending', 'approved', 'integration_refused', 'integration_blocked'].includes(t.status)) throw new UserError(`거절할 수 없는 상태(${t.status})`);
  t.approval = null;
  setStatus(taskExecutor, t, 'rejected', reason || '사용자 거절');
}
