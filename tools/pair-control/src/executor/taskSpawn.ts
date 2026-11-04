import path from 'node:path';
import { spawnSupervised } from './processSupervisor.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { setStatus } from './taskState.ts';
import type { LaunchPlan } from './adapters.ts';
import type { Executor, Task } from './executor.ts';

export function spawnExec(taskExecutor: Executor, t: Task, runId: string, execId: string, plan: LaunchPlan) {
  let command = plan.command, args = plan.args;
  if (t.mode === 'mock') args = [...args, '--counter', path.join(taskExecutor.cfg.stateDir, 'mock-invocations.jsonl')];
  if (t.usesDevelopLock) { command = path.join(t.worktree, 'develop'); args = ['--', plan.command, ...args]; }
  const ex = spawnSupervised(taskExecutor, t, { kind: 'agent', execId, runId, cwd: t.worktree, command, args, env: sanitizedChildEnv(),
    display: t.usesDevelopLock ? ['./develop', '--', ...plan.display] : plan.display });
  t.lastExecId = execId; t.runId = runId; t.runHistory = [...t.runHistory, runId];
  t.result = null; t.approval = null; t.integration = null; t.verification = null; t.review = null; t.handoff = null;
  setStatus(taskExecutor, t, 'running');
  return { ok: true as const, execId, pid: ex.pid };
}
