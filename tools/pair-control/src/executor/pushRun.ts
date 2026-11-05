import { createPushPlan, confirmPushPlan } from './pushPlan.ts';
import { collectPushFacts } from './pushFacts.ts';
import { scanPushHistory } from './pushScan.ts';
import { associatePushTasks, judgePushFindings, dryRunPush } from './pushJudgment.ts';
import { verifyAutomaticPush } from './pushAuthorization.ts';
import { executePush } from './pushExecution.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function runPush(ex: Executor, confirm: string, gate?: { sessionId: string }): Promise<PushRecord> {
  const plan = createPushPlan(ex);
  await collectPushFacts(ex, plan);
  if (plan.commits.length) {
    await associatePushTasks(ex, plan);
    await scanPushHistory(ex, plan);
    judgePushFindings(ex, plan);
    if (!plan.blockers.length) await dryRunPush(ex, plan);
  }
  ex.state.pushPlan = plan; ex.store.save();
  confirmPushPlan(plan, confirm);
  const tasks = gate ? await verifyAutomaticPush(ex, gate.sessionId, plan) : [];
  return executePush(ex, plan, gate?.sessionId, tasks);
}
