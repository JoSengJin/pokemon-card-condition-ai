import * as G from './git.ts';
import { sanitizedChildEnv } from './freeGuard.ts';

export const redactUrl = (u: string) => u.replace(/\/\/[^@/\s]+@/, '//***@');

export const redactText = (s: string) => redactUrl(s).replace(/(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})/g, '[REDACTED]');

export const git = (cwd: string, args: string[], timeout = 60_000) => {
  const env = sanitizedChildEnv();
  env.GIT_TERMINAL_PROMPT = '0';
  if (process.env.SSH_AUTH_SOCK) env.SSH_AUTH_SOCK = process.env.SSH_AUTH_SOCK;
  return G.run('git', args, cwd, timeout, env);
};

export async function lsRemote(cwd: string, remote: string, branch: string): Promise<{ ok: boolean; sha: string | null; detail: string }> {
  const r = await git(cwd, ['ls-remote', remote, `refs/heads/${branch}`]);
  if (r.code !== 0) return { ok: false, sha: null, detail: redactText(r.stderr.trim().slice(0, 300)) };
  const m = r.stdout.trim().split(/\s+/)[0];
  return { ok: true, sha: G.FULL_SHA.test(m ?? '') ? m : null, detail: '' };
}
