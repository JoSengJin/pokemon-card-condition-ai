import { assertMainActive } from './executorPolicy.ts';
import { startReviewJob } from './reviewStart.ts';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { UserError } from './errors.ts';
import { handoffText } from './handoffDocument.ts';
import { handoffMessage } from './handoffRecords.ts';
import type { Executor } from './executor.ts';

export async function handoffToMain(ex: Executor, taskId: string) {
  assertMainActive(ex, '메인 인계');
  const t = ex.task(taskId);
  if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 인계(${t.status})`);
  const r = t.result;
  if (!r?.headSha || !r.commits.length) throw new UserError('인계할 커밋이 없음 — 에이전트가 커밋하지 않았습니다');
  const headResult = await G.run('git', ['rev-parse', '--verify', '--quiet', `refs/heads/${t.branch}^{commit}`], t.worktree);
  const head = headResult.code === 0 && G.FULL_SHA.test(headResult.stdout.trim()) ? headResult.stdout.trim() : null;
  if (head !== r.headSha) throw new UserError('Git 계약 검사 이후 코드 SHA가 바뀜 — "결과 다시 수집" 후 인계');
  const dirty = await G.dirtyFiles(t.worktree);
  if (dirty.length) throw new UserError(`worktree에 미커밋 변경이 있음: ${dirty.slice(0, 5).join(', ')}`);
  if (t.verification?.status === 'running' || t.review?.status === 'running') throw new UserError('작업 테스트나 리뷰가 실행 중');
  if (t.handoff && !t.handoff.cancelledAt && t.handoff.headSha === head) throw new UserError('이미 인계됨(취소 후 다시 인계 가능)');
  const text = await handoffText(t, head, ex.mainAgent);
  const file = path.join(ex.cfg.stateDir, 'handoffs', `${t.taskId}-${head.slice(0, 12)}.md`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  t.handoff = { at: new Date().toISOString(), to: ex.mainAgent, headSha: head, file };
  ex.audit('handoff', { taskId, to: t.handoff.to, headSha: head });
  ex.store.save();
  return { handoff: t.handoff, text, message: handoffMessage(t), autoNote: undefined as string | undefined };
}

export async function handoffToMainAuto(ex: Executor, taskId: string) {
  const handoff = await handoffToMain(ex, taskId);
  // 자동 확인은 구독 로그인 가드를 통과한 실제 CLI로만 한다. 막히면 인계는 유지하고 사람이 붙여 넣는 기존 방식으로 남긴다.
  try { await startReviewJob(ex, taskId, { reviewer: ex.mainAgent, mode: 'real', forHandoff: true }); handoff.autoNote = `${ex.mainAgent} 자동 확인 시작(별도 프로세스, read-only)`; }
  catch (err) { handoff.autoNote = `자동 확인 안 함: ${(err as Error).message} — 안내문을 직접 전달하세요`; }
  return handoff;
}
