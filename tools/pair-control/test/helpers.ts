import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Mastra } from '@mastra/core/mastra';
import { LibSQLStore } from '@mastra/libsql';
import { loadConfig, type PairConfig } from '../src/executor/config.ts';
import { Executor } from '../src/executor/executor.ts';
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
    restart() { ex.stop(); return boot(dir, cfg, fixture, trips); },
    cleanup() {
      ex.stop();
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
  await env.ex.runChecks(id);
  return waitFor(() => { const v = env.ex.task(id).verification; return v && v.status !== 'running' ? v : null; }, `${id} checks`);
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
