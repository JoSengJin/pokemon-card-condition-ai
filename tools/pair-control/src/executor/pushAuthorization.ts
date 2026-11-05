import { pushScope } from './pushOwnership.ts';
import { authorize } from './approvalGate.ts';
import { UserError } from './executor.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function verifyAutomaticPush(ex: Executor, sessionId: string, plan: PushPlan): Promise<string[]> {
  const { unowned, tasks } = await pushScope(ex, plan);
  if (unowned.length) throw new UserError(`승인된 통합 이력에 없는 커밋 ${unowned.length}개(${unowned.slice(0, 3).map((s) => s.slice(0, 8)).join(', ')})가 push 범위에 있음 — 자동 push 보류, 사용자가 직접 확인·push`);
  if (!tasks.length) throw new UserError('push 대상 커밋이 승인된 작업과 연결되지 않음 — 사용자 판단 필요');
  for (const id of tasks) authorize(ex, sessionId, 'integrate_task', id);
  authorize(ex, sessionId, 'push_main', plan.branch);
  return tasks;
}
