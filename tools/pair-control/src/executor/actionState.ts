// 행동 상태의 저장 전이와 결과 수집. 판정·실행은 하지 않는다.
import { note } from './actionPlan.ts';
import type { Executor } from './executor.ts';
import type { ActionResult, ActionWork, MainAction } from './mainTypes.ts';

export interface ActionOwner { actionWork?: ActionWork[] }

export function acceptActions(ex: Executor, owner: ActionOwner, actions: MainAction[]) {
  owner.actionWork = actions.map((action) => ({ action, status: 'accepted' }));
  ex.store.save();
}

export function finishAction(ex: Executor, work: ActionWork, ok: boolean, detail: string, record = true): ActionResult {
  const a = work.action, result = note(String(a.id ?? '?'), String(a.type ?? '?'), ok, detail);
  work.status = 'done'; work.result = result;
  if (record && a.id) ex.runtime.processed[a.id] = result;
  try { ex.audit('main_action', { session: ex.runtime.session?.id, generation: ex.runtime.generation, id: result.id, type: result.type, ok, detail }); } catch { /* 감사 실패가 결과를 바꾸지 않는다 */ }
  ex.store.save();
  return result;
}

export function actionResults(owner: ActionOwner): ActionResult[] {
  const out: ActionResult[] = [];
  for (const work of owner.actionWork ?? []) if (work.result) out.push(work.result);
  return out;
}

export function actionsDone(owner: ActionOwner): boolean {
  for (const work of owner.actionWork ?? []) if (work.status !== 'done') return false;
  return true;
}
