import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { worktreeRoot, branchExists } from './prepareWorktree.ts';
import type { Executor } from './executor.ts';
import type { PrepareInputT } from './prepareInput.ts';

/** 재사용 가능한 이전 준비인지: 같은 브랜치의 등록된 worktree이고, 기준 SHA 이후 커밋은 이 task의 계약 파일만 바꿨으며 미커밋 변경이 없다. */
export async function inspectPreparedWorktree(ex: Executor, input: PrepareInputT, taskId: string, baseSha: string): Promise<true | string | null> {
  if (input.worktree || ex.state.tasks[taskId]) return null;
  const repo = ex.cfg.repo, branch = input.agent + '/' + taskId;
  const worktree = path.join(worktreeRoot(ex), path.basename(repo) + '-' + input.agent + '-' + taskId);
  if (!fs.existsSync(worktree) || !(await branchExists(repo, branch))) return null;
  const real = fs.realpathSync.native(worktree);
  const wt = (await G.worktrees(repo)).find((w) => w.path === real);
  if (!wt || wt.branch !== branch) return '같은 브랜치의 worktree가 아님';
  if (!(await G.isAncestor(real, baseSha, 'HEAD'))) return '기준 SHA가 바뀜';
  const head = await G.revParse(real, 'HEAD');
  const files = await G.changedFiles(real, baseSha, head!);
  if (files.some((f) => f !== `docs/collaboration/tasks/${taskId}.md`)) return '계약 외 변경이 있음';
  if ((await G.dirtyFiles(real)).length) return '미커밋 변경이 있음';
  return true;
}
