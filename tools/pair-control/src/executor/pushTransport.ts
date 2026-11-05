import * as G from './git.ts';
import { sanitizedChildEnv } from './freeGuard.ts';

export const redactUrl = (u: string) => u.replace(/\/\/[^@/\s]+@/, '//***@');

export const redactText = (s: string) => redactUrl(s).replace(/(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})/g, '[REDACTED]');

export function networkEnv() {
  const env = sanitizedChildEnv();
  env.GIT_TERMINAL_PROMPT = '0';
  if (process.env.SSH_AUTH_SOCK) env.SSH_AUTH_SOCK = process.env.SSH_AUTH_SOCK;
  return env;
}

export async function lsRemote(cwd: string, remote: string, branch: string, env: NodeJS.ProcessEnv): Promise<{ ok: boolean; sha: string | null; detail: string }> {
  const r = await G.run('git', ['ls-remote', remote, `refs/heads/${branch}`], cwd, 60_000, env);
  if (r.code !== 0) return { ok: false, sha: null, detail: r.stderr.trim().slice(0, 300) };
  const m = r.stdout.trim().split(/\s+/)[0];
  return { ok: true, sha: G.FULL_SHA.test(m ?? '') ? m : null, detail: '' };
}
