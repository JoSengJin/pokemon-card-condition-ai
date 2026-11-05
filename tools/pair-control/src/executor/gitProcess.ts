import { execFile } from 'node:child_process';

export interface Exec { code: number; stdout: string; stderr: string }

export function run(cmd: string, args: string[], cwd: string, timeoutMs = 60_000, env?: NodeJS.ProcessEnv): Promise<Exec> {
  return new Promise((resolve) => {
    execFile(cmd, args, { cwd, timeout: timeoutMs, maxBuffer: 32 * 1024 * 1024, env: env ?? process.env }, (err: any, stdout, stderr) => {
      resolve({ code: err ? (typeof err.code === 'number' ? err.code : 1) : 0, stdout: String(stdout), stderr: String(stderr) });
    });
  });
}

export const git = (cwd: string, ...args: string[]) => run('git', args, cwd);
