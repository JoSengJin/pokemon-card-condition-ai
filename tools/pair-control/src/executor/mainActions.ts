// 영속 행동 상태를 한 단계씩 진행한다. 실제 관제는 틱마다 한 번 호출하고, 직접 호출 호환 경로만 완료까지 반복한다.
import { authorizeAction } from './actionAuthorize.ts';
import { dispatchAction } from './actionDispatch.ts';
import { advancePushAction } from './actionPush.ts';
import { actionsDone, finishAction, type ActionOwner } from './actionState.ts';
import type { Executor } from './executor.ts';
import type { MainSession } from './mainTypes.ts';

export async function advanceActions(ex: Executor, s: MainSession, owner: ActionOwner): Promise<boolean> {
  for (const work of owner.actionWork ?? []) {
    if (work.status === 'done') continue;
    if (work.status === 'dispatching') {
      if (work.action.type === 'push_main' && work.dispatchLifetime === ex.lifetime && work.pushStage) {
        await advancePushAction(ex, s, work);
        return actionsDone(owner);
      }
      finishAction(ex, work, false, '서버 재시작 전 수행을 시작한 행동 — 결과 불명, 재시도하지 않음');
      return actionsDone(owner);
    }
    if (work.status === 'accepted') await authorizeAction(ex, s, owner, work);
    else if (work.status === 'authorized') await dispatchAction(ex, s, work);
    return actionsDone(owner);
  }
  return true;
}
