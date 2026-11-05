import { getTask } from './executorLookup.ts';
import fs from 'node:fs';
import { appendEvent } from './store.ts';
import { UserError } from './errors.ts';
import type { Executor, Task } from './executor.ts';

export function handoffMessage(t: Task) {
  const h = t.handoff!;
  return `인계됨: ${t.taskId} — 브랜치 ${t.branch}, 전체 SHA ${h.headSha}. 인계 문서: ${h.file} . 작업 위치: ${t.worktree}`;
}

export function readHandoff(ex: Executor, taskId: string) {
  const t = getTask(ex, taskId);
  if (!t.handoff) throw new UserError('인계 기록 없음');
  return { text: fs.existsSync(t.handoff.file) ? fs.readFileSync(t.handoff.file, 'utf8') : '', message: handoffMessage(t), handoff: t.handoff };
}

export function confirmHandoff(ex: Executor, taskId: string, note = '') {
  const t = getTask(ex, taskId);
  const h = t.handoff;
  if (t.status !== 'review_pending' || !h || h.cancelledAt) throw new UserError('유효한 인계가 없음');
  if (h.headSha !== t.result?.headSha) throw new UserError('인계 이후 코드가 바뀜 — 다시 인계');
  h.confirmedAt = new Date().toISOString(); h.note = note.slice(0, 500);
  appendEvent(ex.cfg.stateDir, { type: 'handoff_confirmed', lifetime: ex.lifetime, taskId, headSha: h.headSha });
  ex.store.save();
  return h;
}

export function cancelHandoff(ex: Executor, taskId: string) {
  const t = getTask(ex, taskId);
  const h = t.handoff;
  if (!h || h.cancelledAt) throw new UserError('취소할 인계가 없음');
  if (t.status === 'approved' || t.approval) throw new UserError('승인 후에는 인계를 취소할 수 없음(거절 후 다시 진행)');
  h.cancelledAt = new Date().toISOString();
  ex.audit('handoff_cancelled', { taskId });
  ex.store.save();
  return h;
}
