// 영속 행동 상태를 한 단계씩 진행한다. 실제 관제는 틱마다 한 번 호출하고, 직접 호출 호환 경로만 완료까지 반복한다.
import { authorizeAction } from './actionAuthorize.ts';
import { dispatchAction } from './actionDispatch.ts';
import { acceptActions, actionResults, actionsDone, finishAction, type ActionOwner } from './actionState.ts';
import type { Executor } from './executor.ts';
import type { ActionResult, MainAction, MainSession } from './mainTypes.ts';

export async function advanceActions(ex: Executor, s: MainSession, owner: ActionOwner): Promise<boolean> {
  for (const work of owner.actionWork ?? []) {
    if (work.status === 'done') continue;
    if (work.status === 'dispatching') {
      finishAction(ex, work, false, '서버 재시작 전 수행을 시작한 행동 — 결과 불명, 재시도하지 않음');
      return actionsDone(owner);
    }
    if (work.status === 'accepted') await authorizeAction(ex, s, owner, work);
    else if (work.status === 'authorized') await dispatchAction(ex, s, work);
    return actionsDone(owner);
  }
  return true;
}

/** 기존 내부 호출 호환: 같은 영속 단계 함수를 사용하되 이 호출 안에서 완료까지 진행한다. */
export async function applyActions(ex: Executor, s: MainSession, actions: MainAction[]): Promise<ActionResult[]> {
  const owner: ActionOwner = {};
  acceptActions(ex, owner, actions);
  while (!await advanceActions(ex, s, owner)) { /* 다음 저장 단계를 진행 */ }
  const results = actionResults(owner);
  s.actionResults.push(...results); ex.store.save();
  return results;
}
