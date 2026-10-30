// authorized 행동 하나를 재승인한 뒤 dispatching으로 먼저 저장하고 서비스를 호출한다.
import { authorize } from './approvalGate.ts';
import { finishAction } from './actionState.ts';
import { confirmAction, pushAction } from './mainDispatch.ts';
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
    work.status = 'dispatching'; work.dispatchLifetime = ex.lifetime; ex.store.save();
    try {
      const ops = ex.mainOps;
      if (a.type === 'approve_task' && ops.approve) await ops.approve(target, String(a.sha ?? ''));
      else if (a.type === 'integrate_task' && ops.integrate) await ops.integrate(target);
      else if (a.type === 'assign_task' && ops.assign) await ops.assign(work.input ?? {});
      else if (a.type === 'confirm_handoff') await confirmAction(ex, a, target, !!work.selfReview);
      else if (a.type === 'push_main') await pushAction(ex, s.id, a);
      else throw new UserError(`지원하지 않거나 연결되지 않은 행동(${a.type}) — 수행하지 않음`);
    } catch (e) { finishAction(ex, work, false, `수행 실패: ${(e as Error).message}`); return; }
    const bad = outcomeProblem(ex, a, target);
    const self = a.type === 'confirm_handoff' && ex.state.tasks[target]?.agent === ex.mainAgent ? ' — 자기 확인(독립 검토 아님)' : '';
    finishAction(ex, work, !bad, bad ? `수행했으나 결과가 성공이 아님 — ${bad}` : `${target} ${a.type} 처리 확인${self}`);
  } catch (e) { finishAction(ex, work, false, `예기치 않은 예외: ${(e as Error).message}`); } finally { release(); }
}
