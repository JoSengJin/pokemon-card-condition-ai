import crypto from 'node:crypto';
import { checkout, remoteName } from './pushConfig.ts';
import { collectPushFacts } from './pushFacts.ts';
import { scanPushHistory } from './pushScan.ts';
import { associatePushTasks, judgePushFindings, dryRunPush } from './pushJudgment.ts';
import { UserError } from './executor.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export function createPushPlan(ex: Executor): PushPlan {
  checkout(ex);
  return { id: crypto.randomUUID(), remote: remoteName(ex), remoteUrl: '', branch: ex.cfg.integration.branch, localHead: '', remoteHead: null, commits: [], files: [], tasks: [], findings: [], blockers: [], warnings: [], dryRun: null, revertOf: null, checkedAt: new Date().toISOString() };
}

export async function preflight(ex: Executor): Promise<PushPlan> {
  const plan = createPushPlan(ex);
  await collectPushFacts(ex, plan);
  if (plan.commits.length && plan.commits.length <= 500) {
    await associatePushTasks(ex, plan);
    await scanPushHistory(ex, plan);
    judgePushFindings(ex, plan);
    if (!plan.blockers.length) await dryRunPush(ex, plan);
  } else if (plan.commits.length > 500) plan.blockers.push(`푸시할 커밋이 ${plan.commits.length}개로 너무 많아 이력 점검을 하지 않음 — 나눠서 푸시`);
  ex.state.pushPlan = plan; ex.store.save(); return plan;
}

export function confirmPushPlan(plan: PushPlan, confirm: string): PushPlan {
  const typed = String(confirm ?? '').trim().toLowerCase();
  if (plan.blockers.length) throw new UserError(`푸시할 수 없음: ${plan.blockers.join(' / ')}`);
  if (typed.length < 12 || !plan.localHead.startsWith(typed)) throw new UserError(`확인 입력이 대상 SHA(${plan.localHead.slice(0, 12)}…)의 앞 12자와 다름 — 점검 이후 로컬이 바뀌었을 수 있음`);
  return plan;
}

export async function preparePush(ex: Executor, confirm: string): Promise<PushPlan> {
  return confirmPushPlan(await preflight(ex), confirm);
}
