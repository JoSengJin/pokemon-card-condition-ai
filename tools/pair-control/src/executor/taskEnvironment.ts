import { preflightChecks } from './taskPreflight.ts';
import type { Executor } from './executor.ts';

export async function recheckEnv(owner: Executor, taskId: string) {
  const t = owner.task(taskId);
  t.preflight = await preflightChecks(owner, t);
  owner.store.save();
  return t.envReadiness;
}
