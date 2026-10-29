// 자동 push의 승인 범위: remoteHead..localHead의 모든 커밋이 통합 승인된 작업의 통합 이력(preHead..newHead)에 대응해야 한다.
// 알려진 작업이 하나 포함됐다는 이유로 전체 범위를 승인하지 않는다. 대응하지 않는 커밋이 있으면 자동 push를 보류하고, 사용자가 기존 수동 push 경로로 직접 확인·push한다.
// 이 도구는 별도 범위를 스스로 승인하거나 추정하지 않는다.
import * as G from './git.ts';
import { authorize } from './approvalGate.ts';
import { UserError, type Executor } from './executor.ts';
import type { PushPlan } from './push.ts';

/**
 * push 범위의 각 커밋을 소유 작업에 대응시킨다. 소유 = 통합이 끝나 승인 기록이 있는 작업이 통합 checkout에 만든 커밋(통합 직전 HEAD..통합 뒤 HEAD).
 * 대응하지 않는 커밋과 소유 작업 ID를 돌려준다.
 */
export async function pushScope(ex: Executor, plan: PushPlan): Promise<{ unowned: string[]; tasks: string[] }> {
  const owner = new Map<string, string>();
  for (const t of Object.values(ex.state.tasks)) {
    const i = t.integration;
    if (t.status !== 'integrated' || i?.outcome !== 'integrated' || !i.preHead || !i.newHead || !t.approval) continue;
    for (const sha of await G.commitsBetween(ex.cfg.integration.checkout, i.preHead, i.newHead)) owner.set(sha, t.taskId);
  }
  const unowned: string[] = [], tasks = new Set<string>();
  for (const c of plan.commits) {
    const id = owner.get(c.sha);
    if (id) tasks.add(id); else unowned.push(c.sha);
  }
  return { unowned, tasks: [...tasks] };
}

/** runPush의 push 직전 검증. 범위가 맞지 않거나 승인이 닫혀 있으면 던져 push를 막는다(승인 검사는 마지막에 동기로 해 점검과 실행 사이의 철회를 반영한다). */
export async function verifyPushScope(ex: Executor, sessionId: string, plan: PushPlan): Promise<void> {
  const { unowned, tasks } = await pushScope(ex, plan);
  if (unowned.length) throw new UserError(`승인된 통합 이력에 없는 커밋 ${unowned.length}개(${unowned.slice(0, 3).map((s) => s.slice(0, 8)).join(', ')})가 push 범위에 있음 — 자동 push 보류, 사용자가 직접 확인·push`);
  if (!tasks.length) throw new UserError('push 대상 커밋이 승인된 작업과 연결되지 않음 — 사용자 판단 필요');
  for (const id of tasks) authorize(ex, sessionId, 'integrate_task', id);
  authorize(ex, sessionId, 'push_main', plan.branch);
}
