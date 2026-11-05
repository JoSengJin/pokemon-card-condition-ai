import { getTask } from '../src/executor/executorLookup.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { runChecks } from '../src/executor/verificationStart.ts';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Mastra } from '@mastra/core/mastra';
import { LibSQLStore } from '@mastra/libsql';
import { loadConfig, type PairConfig } from '../src/executor/config.ts';
import { Executor } from '../src/executor/executor.ts';
import { authorizeAction } from '../src/executor/actionAuthorize.ts';
import { dispatchAction } from '../src/executor/actionDispatch.ts';
import { advancePushAction } from '../src/executor/actionPush.ts';
import { acceptActions, actionResults, actionsDone, finishAction, type ActionOwner } from '../src/executor/actionState.ts';
import type { MainAction, MainSession } from '../src/executor/mainTypes.ts';
import type { Alert } from '../src/executor/freeGuard.ts';
import { bindRuntime } from '../src/runtime.ts';
import { pairTaskWorkflow, prepareTaskWorkflow } from '../src/workflow.ts';
// @ts-ignore plain JS helper
import { makeFixture } from '../scripts/fixture-lib.mjs';

process.env.PAIR_CONTROL_NO_NOTIFY = '1';
export const toolRoot = path.resolve(import.meta.dirname, '..');

export interface Env {
  dir: string; cfg: PairConfig; ex: Executor; fixture: any; trips: Alert[];
  restart(): Env; cleanup(): void;
}

/** 테스트가 영속 행동 상태를 한 단계 진행한다. 운영 경로는 pipelineTick이 저장 상태를 직접 라우팅한다. */
export async function advanceActions(ex: Executor, s: MainSession, owner: ActionOwner): Promise<boolean> {
  for (const work of owner.actionWork ?? []) {
    if (work.status === 'done') continue;
    if (work.status === 'dispatching') {
      if (work.action.type === 'push_main' && work.dispatchLifetime === ex.lifetime && work.pushStage) await advancePushAction(ex, s, work);
      else finishAction(ex, work, false, '서버 재시작 전 수행을 시작한 행동 — 결과 불명, 재시도하지 않음');
    } else if (work.status === 'accepted') await authorizeAction(ex, s, owner, work);
    else if (work.status === 'authorized') await dispatchAction(ex, s, work);
    return actionsDone(owner);
  }
  return true;
}

/** 직접 행동 회귀용 호환 도우미. */
export async function applyActions(ex: Executor, s: MainSession, actions: MainAction[]) {
  const owner: { actionWork?: MainSession['actionWork'] } = {};
  acceptActions(ex, owner, actions);
  while (!await advanceActions(ex, s, owner)) { /* 저장 단계를 끝까지 진행 */ }
  const results = actionResults(owner);
  s.actionResults.push(...results); ex.store.save();
  return results;
}

function boot(dir: string, cfg: PairConfig, fixture: any, trips: Alert[]): Env {
  const ex = new Executor(cfg, { onTrip: (a) => trips.push(a) });
  const mastra = new Mastra({
    workflows: { pairTaskWorkflow, prepareTaskWorkflow },
    storage: new LibSQLStore({ id: 'test', url: `file:${path.join(cfg.stateDir, 'mastra.db')}` }),
    logger: false,
  });
  bindRuntime(ex, mastra);
  const env: Env = {
    dir, cfg, ex, fixture, trips,
    // 서버 비정상 종료 흉내: 자식 프로세스는 건드리지 않고 감시만 멈춘 뒤 같은 상태 폴더로 새 실행기를 띄운다.
    restart() { stop(ex, ); return boot(dir, cfg, fixture, trips); },
    cleanup() {
      stop(ex, );
      for (const e of Object.values(ex.state.executions)) { try { process.kill(-e.pgid, 'SIGKILL'); } catch { /* gone */ } }
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
  return env;
}

export const fakeCli = { claude: path.join(toolRoot, 'test', 'fake-cli', 'claude'), codex: path.join(toolRoot, 'test', 'fake-cli', 'codex') };

export function setup(over: Partial<PairConfig> = {}): Env {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pair-control-test-'));
  const fixture = makeFixture(path.join(dir, 'fx'), toolRoot);
  fs.mkdirSync(path.join(dir, 'home'), { recursive: true });
  const cfg = loadConfig({
    toolRoot, stateDir: path.join(dir, 'state'), repo: fixture.repo,
    integration: { checkout: fixture.repo, branch: 'main' }, worktreeRoot: path.join(dir, 'fx'), port: 4111, allowRealModelCalls: false, confirmedSubscriptionAuth: false, cli: {},
    homeDir: path.join(dir, 'home'), ...over,
  });
  return boot(dir, cfg, fixture, []);
}

export function task(env: Env, name: string, extra: Record<string, unknown> = {}) {
  const w = env.fixture.worktrees[name];
  return {
    taskId: name, agent: w.agent, branch: w.branch, worktree: w.path, baseSha: env.fixture.baseSha,
    allowedFiles: ['src_a/'], goal: `${name} 목표`, mockScenario: 'success',
    checks: [{ id: 'ws', name: '공백 오류 검사', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'] }],
    ...extra,
  };
}

/** 사용자가 '작업 테스트 실행'을 누른 것과 같다. 끝날 때까지 기다린다. */
export async function verify(env: Env, id: string) {
  await runChecks(env.ex, id);
  return waitFor(() => { const v = getTask(env.ex, id).verification; return v && v.status !== 'running' ? v : null; }, `${id} checks`);
}

export async function waitFor<T>(fn: () => T | Promise<T>, label: string, timeoutMs = 15_000): Promise<NonNullable<T>> {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const v = await fn();
    if (v) return v as NonNullable<T>;
    if (Date.now() > end) throw new Error(`timeout: ${label}`);
    await new Promise((r) => setTimeout(r, 100));
  }
}

export const alive = (pid: number) => { try { process.kill(pid, 0); return true; } catch { return false; } };

export function invocations(env: Env) {
  const f = path.join(env.cfg.stateDir, 'mock-invocations.jsonl');
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trim().split('\n').filter(Boolean).length : 0;
}

/** 키 모양의 가짜 비밀값. 리터럴로 두면 이 저장소의 푸시 점검(비밀 패턴)에 걸리므로 실행 시점에 조립한다. */
export const fakeSecret = (tag: string) => ['sk', tag, 'a1b2c3d4e5f6g7h8i9j0k1l2'].join('-');
