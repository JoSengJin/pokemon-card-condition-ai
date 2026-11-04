import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { appendEvent, writeJsonAtomic } from './store.ts';
import type { Executor, Task, ExecKind, Execution } from './executor.ts';

export function spawnSupervised(ex: Executor, t: Pick<Task, 'taskId' | 'agent' | 'mode'>, o: { kind: ExecKind; execId?: string; runId: string; cwd: string; command: string; args: string[]; env: NodeJS.ProcessEnv; display: string[]; checkId?: string; sha?: string }) {
  const execId = o.execId ?? crypto.randomUUID();
  const dir = path.join(ex.cfg.stateDir, 'runs', execId);
  fs.mkdirSync(dir, { recursive: true });
  const token = crypto.randomUUID();
  const spec = { execId, token, cwd: o.cwd, command: o.command, args: o.args, env: o.env, logPath: path.join(dir, 'output.log'), exitPath: path.join(dir, 'exit.json') };
  const specPath = path.join(dir, 'spec.json');
  writeJsonAtomic(specPath, spec);
  fs.writeFileSync(spec.logPath, '');
  const sup = spawn(process.execPath, [ex.supervisorPath, specPath], { cwd: o.cwd, detached: true, stdio: 'ignore', env: o.env });
  sup.on('error', (e) => appendEvent(ex.cfg.stateDir, { type: 'supervisor_spawn_error', lifetime: ex.lifetime, execId, error: e.message })); // 정리 도중 등 시작 실패가 프로세스 전체 예외로 번지지 않게 기록만 한다
  sup.unref();
  if (!sup.pid) throw new Error('감독 프로세스 시작 실패');
  const execution: Execution = {
    kind: o.kind, checkId: o.checkId, sha: o.sha,
    execId, taskId: t.taskId, runId: o.runId, token, agent: t.agent, mode: t.mode, display: o.display,
    pid: sup.pid, pgid: sup.pid, startedAt: new Date().toISOString(), status: 'running', cancelRequested: false,
    observedAfterRestart: false, serverLifetime: ex.lifetime, logPath: spec.logPath, exitPath: spec.exitPath, specPath,
    tokens: '미측정', cost: '미측정',
  };
  ex.state.executions[execId] = execution;
  appendEvent(ex.cfg.stateDir, { type: 'exec_started', lifetime: ex.lifetime, taskId: t.taskId, kind: o.kind, execId, runId: o.runId, pid: execution.pid, display: execution.display });
  ex.store.save();
  ex.ensureWatcher();
  return execution;
}
