// authorized 행동 하나를 재승인한 뒤 dispatching으로 먼저 저장하고 서비스를 호출한다.
import { approve } from './taskApproval.ts';
import { getTask } from './executorLookup.ts';
import { prepareTask, startTask } from '../runtimeTasks.ts';
import { authorize } from './approvalGate.ts';
import { finishAction } from './actionState.ts';
import { confirmAction } from './mainDispatch.ts';
import { outcomeProblem } from './mainOutcome.ts';
import { lock } from './mainSerial.ts';
import { UserError, type Executor } from './executor.ts';
import type { ActionWork, MainSession } from './mainTypes.ts';

export async function dispatchAction(ex: Executor, s: MainSession, work: ActionWork) {
  if (work.status !== 'authorized') return;
  const release = await lock(ex), a = work.action, target = String(work.target ?? '');
  try {
    const rt = ex.runtime;
    if (rt.session?.id !== s.id || rt.generation !== s.generation || rt.frozen) { finishAction(ex, work, false, '이전 세대의 메인이거나 교대 진행 중 — 상태를 바꾸지 못함', false); return; }
    try { authorize(ex, s.id, a.type, target, a.sha); } catch (e) { finishAction(ex, work, false, (e as Error).message); return; }
    const origin = { sessionId: s.id, generation: s.generation, lifetime: ex.lifetime, action: a.type, target, sha: a.sha };
    work.status = 'dispatching'; work.dispatchLifetime = ex.lifetime; ex.store.save();
    try {
      if (a.type === 'approve_task') {
        if (!ex.resumer) throw new UserError('workflow 재개 서비스가 연결되지 않음');
        const approval = await approve(ex, target, String(a.sha ?? ''), { requireHandoff: true, origin });
        await ex.resumer(getTask(ex, target).runId!, 'review-gate', { decision: 'approve', sha: approval.sha }, origin);
      } else if (a.type === 'integrate_task') {
        const task = getTask(ex, target);
        if (task.status !== 'approved') throw new UserError(`승인된 상태가 아님(${task.status})`);
        if (!ex.resumer) throw new UserError('workflow 재개 서비스가 연결되지 않음');
        await ex.resumer(task.runId!, 'integrate-gate', { action: 'integrate' }, origin);
      } else if (a.type === 'assign_task') {
        const result = await prepareTask(work.input ?? {}, origin);
        if (work.input?.start !== false) await startTask(result.taskId!, origin);
      }
      else if (a.type === 'confirm_handoff') await confirmAction(ex, a, target, !!work.selfReview, origin);
      else if (a.type === 'push_main') {
        const sha = String(a.sha ?? '').toLowerCase();
        if (sha.length < 12) throw new UserError('push 확인 SHA는 앞 12자 이상이어야 함');
        work.pushStage = 'plan'; ex.store.save(); return;
      }
      else throw new UserError(`지원하지 않거나 연결되지 않은 행동(${a.type}) — 수행하지 않음`);
    } catch (e) { finishAction(ex, work, false, `수행 실패: ${(e as Error).message}`); return; }
    const bad = outcomeProblem(ex, a, target);
    const self = a.type === 'confirm_handoff' && ex.state.tasks[target]?.agent === ex.mainAgent ? ' — 자기 확인(독립 검토 아님)' : '';
    finishAction(ex, work, !bad, bad ? `수행했으나 결과가 성공이 아님 — ${bad}` : `${target} ${a.type} 처리 확인${self}`);
  } catch (e) { finishAction(ex, work, false, `예기치 않은 예외: ${(e as Error).message}`); } finally { release(); }
}
