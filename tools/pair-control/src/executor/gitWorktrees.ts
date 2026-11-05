import fs from 'node:fs';
import { run } from './gitProcess.ts';

export async function worktrees(repo: string): Promise<{ path: string; branch: string | null; head: string | null }[]> {
  const r = await run('git', ['worktree', 'list', '--porcelain'], repo);
  if (r.code !== 0) return [];
  const out: { path: string; branch: string | null; head: string | null }[] = [];
  for (const block of r.stdout.split('\n\n')) {
    const lines = block.split('\n');
    const wt = lines.find((l) => l.startsWith('worktree '));
    if (!wt) continue;
    const br = lines.find((l) => l.startsWith('branch '));
    const head = lines.find((l) => l.startsWith('HEAD '));
    out.push({
      path: fs.realpathSync.native(wt.slice(9)),
      branch: br ? br.slice(7).replace(/^refs\/heads\//, '') : null,
      head: head ? head.slice(5) : null,
    });
  }
  return out;
}
