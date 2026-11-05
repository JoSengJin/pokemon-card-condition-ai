// accepted 행동 하나를 검사하고 authorized로 저장한다. 실제 서비스는 호출하지 않는다.
import { authorize } from './approvalGate.ts';
import { PENDING, plan, uncertain } from './actionPlan.ts';
import { finishAction, type ActionOwner } from './actionState.ts';
import { lock } from './mainSerial.ts';
import { suggestTaskId } from './prepare.ts';
import type { Executor } from './executor.ts';
import type { ActionWork, MainSession } from './mainTypes.ts';

function shouldSkip(owner: ActionOwner, work: ActionWork) {
  let failed = false;
  for (const row of owner.actionWork ?? []) {
    if (row === work) break;
    const result = row.result;
    const sameTask = !!work.action.taskId && row.action.taskId === work.action.taskId;
    if (result && !result.ok && (sameTask || work.action.type === 'push_main') && result.type !== 'note') failed = true;
  }
  return failed;
}

export async function authorizeAction(ex: Executor, s: MainSession, owner: ActionOwner, work: ActionWork) {
  const a = work.action;
  if (work.status !== 'accepted') return;
  if (!a.id || !a.type) { finishAction(ex, work, false, '행동 ID·종류가 없음'); return; }
  if (shouldSkip(owner, work) && !ex.runtime.processed[a.id]) { finishAction(ex, work, false, '같은 작업(또는 push 앞)의 이전 행동이 실패해 수행하지 않음'); return; }
  const release = await lock(ex);
  try {
    const rt = ex.runtime;
    if (rt.session?.id !== s.id || rt.generation !== s.generation || rt.frozen) { finishAction(ex, work, false, '이전 세대의 메인이거나 교대 진행 중 — 상태를 바꾸지 못함', false); return; }
    if (rt.processed[a.id]) { finishAction(ex, work, false, '중복 행동 ID — 다시 수행하지 않음', false); return; }
    rt.processed[a.id] = { id: a.id, type: a.type, ok: false, detail: PENDING, at: new Date().toISOString() };
    ex.store.save();
    if (a.type === 'note') { finishAction(ex, work, true, '기록만 함(상태 변경 없음)'); return; }
    const hold = uncertain(ex, a);
    if (hold) { finishAction(ex, work, false, hold); return; }
    const plannedAction = a.type === 'assign_task' && !a.input?.taskId && !a.taskId
      ? { ...a, input: { ...a.input, taskId: await suggestTaskId(ex, String(a.input?.agent ?? 'claude')) } } : a;
    const p = plan(ex, plannedAction);
    if ('error' in p) { finishAction(ex, work, false, p.error); return; }
    try {
      const ap = authorize(ex, s.id, a.type, p.target, a.sha);
      work.target = p.target; work.input = p.input; work.selfReview = !!ap.requires?.selfReview; work.status = 'authorized';
      ex.store.save();
    } catch (e) { finishAction(ex, work, false, (e as Error).message); }
  } catch (e) { finishAction(ex, work, false, `예기치 않은 예외: ${(e as Error).message}`); } finally { release(); }
}
