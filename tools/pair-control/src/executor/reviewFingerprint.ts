import * as G from './git.ts';
import { parseDirtyFiles } from './gitFiles.ts';
import type { Task } from './executor.ts';

export async function worktreeFingerprint(t: Task) {
  const result = await G.run('git', ['rev-parse', '--verify', '--quiet', 'HEAD^{commit}'], t.worktree);
  const sha = result.stdout.trim(), head = result.code === 0 && G.FULL_SHA.test(sha) ? sha : null;
  const status = await G.run('git', ['status', '--porcelain=v1', '-z', '--untracked-files=all'], t.worktree);
  const dirty = parseDirtyFiles(status);
  return `${head}|${dirty.sort().join(',')}`;
}
