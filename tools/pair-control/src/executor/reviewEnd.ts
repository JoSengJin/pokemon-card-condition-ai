import fs from 'node:fs';
import path from 'node:path';
import { worktreeFingerprint } from './reviewFingerprint.ts';
import type { Executor, Execution, Task, ReviewRecord, ReviewVerdict } from './executor.ts';

export async function onReviewEnd(taskExecutor: Executor, t: Task, ex: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
  const rv = t.review;
  taskExecutor.locks.release(`review:${t.taskId}`, 'execId', ex.runId);
  if (!rv || rv.reviewId !== ex.runId) { taskExecutor.store.save(); return; }
  rv.endedAt = new Date().toISOString();
  let status: ReviewRecord['status'], note: string | undefined, verdict: ReviewVerdict | null = null, summary: string | undefined;
  if (r.unknown) { status = 'unknown'; note = '리뷰 프로세스가 종료 기록 없이 사라짐(결과 불명)'; }
  else if (r.cancelled) { status = 'cancelled'; note = '사용자 중단'; }
  else if ((await worktreeFingerprint(t)) !== rv.worktreeFingerprint) { status = 'failed'; note = '리뷰 중 구현 worktree가 바뀜 — 결과를 쓰지 않음'; }
  else if (r.code !== 0) { status = 'failed'; note = `리뷰 CLI 종료코드 ${r.code}`; }
  else {
    let parsed: any = null;
    const file = path.join(rv.bundleDir, 'review-result.json');
    try { parsed = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {
      const lines = (fs.existsSync(ex.logPath) ? fs.readFileSync(ex.logPath, 'utf8') : '').trim().split('\n').reverse();
      for (const line of lines) { try { const value = JSON.parse(line); if (value && typeof value === 'object' && 'verdict' in value) { parsed = value; break; } } catch { /* next */ } }
    }
    const verdicts: ReviewVerdict[] = ['approve', 'changes_requested', 'insufficient_evidence'];
    if (!parsed || !verdicts.includes(parsed.verdict)) { status = 'failed'; note = '판정 형식을 읽지 못함 — "통과" 같은 문구만으로는 판정으로 보지 않음'; }
    else if (parsed.sha !== rv.sha) { status = 'failed'; note = `다른 SHA(${String(parsed.sha).slice(0, 12)})에 대한 판정 — 사용하지 않음`; }
    else { status = 'done'; note = ex.observedAfterRestart ? '서버 재시작 후 종료 관찰' : undefined; verdict = parsed.verdict; summary = String(parsed.summary ?? '').slice(0, 2000); }
  }
  rv.status = status; rv.note = note; rv.verdict = verdict; rv.summary = summary;
  taskExecutor.audit('review_finished', { taskId: t.taskId, reviewId: rv.reviewId, status, verdict });
  taskExecutor.store.save();
  settleHandoffReview(taskExecutor, t, rv);
}

export function settleHandoffReview(taskExecutor: Executor, t: Task, rv: ReviewRecord) {
  const h = t.handoff;
  if (!rv.forHandoff || !h || h.cancelledAt || h.confirmedAt || h.to !== rv.reviewer || h.headSha !== rv.sha || t.status !== 'review_pending') return;
  const at = new Date().toISOString();
  if (rv.status === 'done' && rv.verdict === 'approve' && h.headSha === t.result?.headSha) {
    h.confirmedAt = at; h.auto = true; delete h.autoResult;
    h.note = `자동 확인: 별도 ${rv.reviewer} 프로세스(리뷰 ${rv.reviewId.slice(0, 8)})의 approve — 대화 중인 메인 세션의 확인이 아님`;
    taskExecutor.audit('handoff_confirmed', { taskId: t.taskId, headSha: h.headSha, auto: true });
  } else {
    h.autoResult = { at, status: rv.status, verdict: rv.verdict ?? null, summary: (rv.summary ?? rv.note ?? '').slice(0, 600) };
    taskExecutor.audit('handoff_auto_result', { taskId: t.taskId, headSha: h.headSha, status: rv.status, verdict: rv.verdict ?? null });
  }
  taskExecutor.store.save();
}
