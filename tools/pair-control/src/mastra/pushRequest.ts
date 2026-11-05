// 수동 HTTP 요청의 오케스트레이터. 점검 단계와 실행 단계를 같은 층에서 순서대로 호출한다.
import { createPushPlan, confirmPushPlan } from '../executor/pushPlan.ts';
import { collectPushFacts } from '../executor/pushFacts.ts';
import { scanPushHistory } from '../executor/pushScan.ts';
import { associatePushTasks, judgePushFindings, dryRunPush } from '../executor/pushJudgment.ts';
import { executePush } from '../executor/pushExecution.ts';
import { body } from './apiBase.ts';
import { executor } from './serverContext.ts';

export async function pushRequest(context: any) {
  const confirm = String((await body(context)).confirm ?? ''), plan = createPushPlan(executor);
  await collectPushFacts(executor, plan);
  if (plan.commits.length) {
    await associatePushTasks(executor, plan);
    await scanPushHistory(executor, plan);
    judgePushFindings(executor, plan);
    if (!plan.blockers.length) await dryRunPush(executor, plan);
  }
  executor.state.pushPlan = plan; executor.store.save();
  confirmPushPlan(plan, confirm);
  return executePush(executor, plan);
}
