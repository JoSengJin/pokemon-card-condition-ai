import { PREP, whyClosed } from './approvalScope.ts';
import type { RuntimeOrigin } from '../runtimeRequests.ts';
import { getTask } from './executorLookup.ts';
import { ensureWatcher } from './monitorSchedule.ts';
import crypto from 'node:crypto';
import * as G from './git.ts';
import { checkVenv, neededEnv } from './envcheck.ts';
import { resolveCheck } from './checkCommand.ts';
import { UserError } from './errors.ts';
import type { Executor, CheckRun } from './executor.ts';

export async function runChecks(taskExecutor: Executor, taskId: string, origin?: Pick<RuntimeOrigin, 'sessionId' | 'generation' | 'lifetime'>) {
  const t = getTask(taskExecutor, taskId);
  if (taskExecutor.guardAlert) throw new UserError('과금 신호 감지 상태 — 실행하지 않음');
  if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 작업 테스트를 실행(${t.status})`);
  if (!t.checks.length) throw new UserError('계약에 작업 테스트가 없음 — 승인할 수 없음(검사를 포함해 새 작업으로 준비)');
  if (t.verification?.status === 'running') throw new UserError('작업 테스트가 이미 실행 중');
  const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
  if (!head || head !== t.result?.headSha) throw new UserError('Git 계약 검사 이후 코드 SHA가 바뀜 — 결과 재수집 필요');
  if ((await G.dirtyFiles(t.worktree)).length) throw new UserError('worktree에 미커밋 변경이 있음 — 커밋된 코드만 검사');
  const envr = await checkVenv(t.worktree, neededEnv(t, t.usesDevelopLock), t.requiredModules);
  if (taskExecutor.stopped || taskExecutor.guardAlert) throw new UserError('실행기 중단 또는 과금 가드 상태 — 작업 테스트를 시작하지 않음');
  if (t.status !== 'review_pending' || t.result?.headSha !== head) throw new UserError('검사 준비 중 작업 상태·SHA가 바뀜 — 시작하지 않음');
  if (origin) {
    const rt = taskExecutor.runtime;
    if (taskExecutor.lifetime !== origin.lifetime || rt.session?.id !== origin.sessionId || rt.generation !== origin.generation || rt.frozen) throw new UserError('자동 검사 준비 중 메인 세션·세대가 바뀜 — 시작하지 않음');
    const hold = whyClosed(taskExecutor, origin.sessionId, PREP, taskId);
    if (hold) throw new UserError(hold);
  }
  t.envReadiness = envr;
  if (!envr.ready) throw new UserError(`실행 환경 미준비: ${envr.checks.filter((c) => !c.ok).map((c) => `${c.name}(${c.detail})`).join(', ')}`);
  const runId = crypto.randomUUID();
  const vars = { base: t.baseSha, contract: t.contractSha, head };
  const items: CheckRun[] = t.checks.map((c) => ({ id: c.id, name: c.name, display: resolveCheck(t.worktree, c, vars).display, cwd: c.cwd, status: 'pending', sha: head }));
  const names = [`task:${t.taskId}`, `worktree:${t.worktree}`];
  const got: string[] = [];
  for (const n of names) {
    if (!taskExecutor.locks.acquire(n, { execId: runId, taskId, kind: 'check', lifetime: taskExecutor.lifetime })) {
      for (const g of got) taskExecutor.locks.release(g, 'execId', runId);
      throw new UserError(`잠금 사용 중: ${n}`);
    }
    got.push(n);
  }
  t.verification = { runId, sha: head, contractHash: t.contractHash, status: 'running', items, startedAt: new Date().toISOString() };
  taskExecutor.audit('checks_started', { taskId, runId, sha: head });
  taskExecutor.store.save();
  ensureWatcher(taskExecutor, );
  return t.verification;
}
