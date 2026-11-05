import { getTask } from './executorLookup.ts';
import { preflightChecks } from './taskPreflight.ts';
import type { Executor } from './executor.ts';

export async function recheckEnv(owner: Executor, taskId: string) {
  const t = getTask(owner, taskId);
  t.preflight = await preflightChecks(owner, t);
  owner.store.save();
  return t.envReadiness;
}
