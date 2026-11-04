import * as G from './git.ts';
import type { Task } from './executor.ts';

export async function worktreeFingerprint(t: Task) {
  const head = await G.revParse(t.worktree, 'HEAD');
  const dirty = await G.dirtyFiles(t.worktree);
  return `${head}|${dirty.sort().join(',')}`;
}
