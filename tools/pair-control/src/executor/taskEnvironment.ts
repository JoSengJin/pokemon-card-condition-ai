import type { Executor } from './executor.ts';

export async function recheckEnv(owner: Executor, taskId: string) {
  const t = owner.task(taskId);
  t.preflight = await owner.preflightChecks(t);
  owner.store.save();
  return t.envReadiness;
}
