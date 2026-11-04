import crypto from 'node:crypto';
import * as G from './git.ts';
import type { Executor, Task } from './executor.ts';

export async function integrationState(taskExecutor: Executor, t: Task, sha: string) {
  const changed = await G.run('git', ['diff', '--name-only', '-z', `${t.baseSha}..${sha}`], t.worktree);
  const files = changed.stdout.split('\0').filter(Boolean).sort();
  const base = await G.run('git', ['rev-parse', '--verify', '--quiet', `refs/heads/${taskExecutor.cfg.integration.branch}^{commit}`], taskExecutor.cfg.integration.checkout);
  const baseHead = G.FULL_SHA.test(base.stdout.trim()) ? base.stdout.trim() : null;
  return { files, filesHash: crypto.createHash('sha256').update(files.join('\0')).digest('hex'), baseHead };
}
