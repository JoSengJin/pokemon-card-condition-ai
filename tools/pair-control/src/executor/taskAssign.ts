import { authorize } from './approvalGate.ts';
import type { RuntimeOrigin } from '../runtimeRequests.ts';
import { assertMainActive } from './executorPolicy.ts';
import { preflightChecks } from './taskPreflight.ts';
import fs from 'node:fs';
import { needsDevelopLock, TaskInput } from './contract.ts';
import { commitContract, contractPath } from './contractFile.ts';
import { UserError } from './errors.ts';
import type { Executor, Task } from './executor.ts';

export async function assign(taskExecutor: Executor, raw: unknown, origin?: RuntimeOrigin): Promise<Task> {
  assertMainActive(taskExecutor, '작업 배정');
  if (origin) authorize(taskExecutor, origin.sessionId, origin.action, origin.target, origin.sha, origin);
  const generation = taskExecutor.runtime.generation;
  const parsed = TaskInput.safeParse(raw);
  if (!parsed.success) throw new UserError(parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
  const input = parsed.data;
  if (taskExecutor.state.tasks[input.taskId]) throw new UserError(`이미 배정된 task ID: ${input.taskId}`);
  const worktree = fs.existsSync(input.worktree) ? fs.realpathSync.native(input.worktree) : input.worktree;
  const now = new Date().toISOString();
  const t: Task = { ...input, worktree, status: 'assigned', createdAt: now, updatedAt: now, runHistory: [], usesDevelopLock: needsDevelopLock(input),
    contractPath: contractPath(input.taskId), contractSha: '', contractHash: '' };
  // 계약은 등록된 별도 worktree의 작업 브랜치에만 커밋한다(main·통합 checkout 금지).
  const must = ['설정', 'worktree 등록', '기본 checkout 분리', '브랜치', '기준 SHA', 'Git 진행 중 작업 없음'];
  const pre = (await preflightChecks(taskExecutor, t)).filter((c) => must.includes(c.name) && !c.ok);
  if (pre.length) throw new UserError(`계약을 커밋할 수 없음: ${pre.map((c) => `${c.name}(${c.detail})`).join(', ')}`);
  try {
    assertMainActive(taskExecutor, '작업 계약', generation);
    if (origin) authorize(taskExecutor, origin.sessionId, origin.action, origin.target, origin.sha, origin);
    const cc = await commitContract(worktree, input, { ex: taskExecutor, origin, generation });
    t.contractSha = cc.contractSha; t.contractHash = cc.contractHash;
    taskExecutor.audit('contract_committed', { taskId: t.taskId, contractSha: cc.contractSha, reused: cc.reused });
  } catch (err) { throw new UserError((err as Error).message); }
  t.preflight = await preflightChecks(taskExecutor, t);
  assertMainActive(taskExecutor, '작업 배정', generation);
  if (origin) authorize(taskExecutor, origin.sessionId, origin.action, origin.target, origin.sha, origin);
  if (taskExecutor.state.tasks[t.taskId]) throw new UserError(`준비 중 이미 배정된 task ID: ${t.taskId}`);
  taskExecutor.state.tasks[t.taskId] = t;
  taskExecutor.audit('task_assigned', { taskId: t.taskId, agent: t.agent, mode: t.mode, branch: t.branch, baseSha: t.baseSha });
  taskExecutor.store.save();
  return t;
}
