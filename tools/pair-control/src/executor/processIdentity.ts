import { execFileSync } from 'node:child_process';
import type { Executor, Execution } from './executor.ts';

export function alive(taskExecutor: Executor, pid: number) { try { process.kill(pid, 0); return true; } catch (e: any) { return e.code === 'EPERM'; } }

export function groupAlive(taskExecutor: Executor, pgid: number) { try { process.kill(-pgid, 0); return true; } catch (e: any) { return e.code === 'EPERM'; } }

export function ownsLeader(taskExecutor: Executor, ex: Execution): boolean | null {
  try {
    const out = execFileSync('ps', ['-o', 'pgid=,command=', '-p', String(ex.pid)]).toString().trim();
    if (!out) return null;
    const [pgid, ...cmd] = out.split(/\s+/);
    return Number(pgid) === ex.pgid && cmd.join(' ').includes(ex.specPath);
  } catch { return null; }
}
