// 자동 push 행동의 저장 단계. 각 호출은 저장 상태 하나만 읽어 다음 단계 하나를 기록한다.
import { finishAction } from './actionState.ts';
import { executePush, preparePush, verifyAutomaticPush } from './push.ts';
import { UserError, type Executor } from './executor.ts';
import type { ActionWork, MainSession } from './mainTypes.ts';

export async function advancePushAction(ex: Executor, s: MainSession, work: ActionWork) {
  const stage = work.pushStage, sha = String(work.action.sha ?? '').toLowerCase();
  try {
    if (stage === 'plan') {
      const plan = await preparePush(ex, sha);
      work.pushPlanId = plan.id; work.pushStage = 'scope'; ex.store.save(); return;
    }
    const plan = ex.state.pushPlan;
    if (!plan || plan.id !== work.pushPlanId) throw new UserError('저장된 push 계획이 없거나 바뀜 — 실행하지 않음');
    if (stage === 'scope') {
      work.pushTasks = await verifyAutomaticPush(ex, s.id, plan);
      work.pushStage = 'lock'; ex.store.save(); return;
    }
    if (stage === 'lock') {
      work.pushStage = 'exec'; ex.store.save();
      const pushed = await executePush(ex, plan, s.id, work.pushTasks);
      if (pushed.status !== 'pushed_verified') throw new UserError(`push가 검증되지 않음(${pushed.status}): ${pushed.detail}`);
      finishAction(ex, work, true, `${plan.branch} push_main 처리 확인`); return;
    }
    throw new UserError('push 실행 시작 뒤 결과 기록이 없음 — 재시도하지 않음');
  } catch (e) { finishAction(ex, work, false, `수행 실패: ${(e as Error).message}`); }
}
