import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const executeFile = promisify(execFile);

export interface Exec { code: number; stdout: string; stderr: string }

export async function run(cmd: string, args: string[], cwd: string, timeoutMs = 60_000, env?: NodeJS.ProcessEnv): Promise<Exec> {
  try {
    const { stdout, stderr } = await executeFile(cmd, args, { cwd, timeout: timeoutMs, maxBuffer: 32 * 1024 * 1024, env: env ?? process.env });
    return { code: 0, stdout: String(stdout), stderr: String(stderr) };
  } catch (error) {
    const result = error as { code?: unknown; stdout?: unknown; stderr?: unknown };
    return { code: typeof result.code === 'number' ? result.code : 1, stdout: String(result.stdout ?? ''), stderr: String(result.stderr ?? '') };
  }
}

export const git = (cwd: string, ...args: string[]) => run('git', args, cwd);
