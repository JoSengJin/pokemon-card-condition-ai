import { buildStartPrompt, type PromptOptions } from './startPrompt.ts';
import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export async function startPrompt(ex: Executor, taskId: string, o: PromptOptions = {}) {
  const t = ex.task(taskId);
  try { return await buildStartPrompt(t, ex.mainAgent, o); } catch (err) { throw new UserError((err as Error).message); }
}
