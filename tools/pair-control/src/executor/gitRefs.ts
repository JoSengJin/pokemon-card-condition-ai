import fs from 'node:fs';
import path from 'node:path';
import { run } from './gitProcess.ts';

export const FULL_SHA = /^[0-9a-f]{40}$/;

export async function revParse(cwd: string, ref: string): Promise<string | null> {
  const r = await run('git', ['rev-parse', '--verify', '--quiet', `${ref}^{commit}`], cwd); // git 래퍼를 거치지 않고 직접 실행(호출 전이 1회 감소)
  const sha = r.stdout.trim();
  return r.code === 0 && FULL_SHA.test(sha) ? sha : null;
}

export async function currentBranch(cwd: string): Promise<string | null> {
  const r = await run('git', ['symbolic-ref', '--quiet', '--short', 'HEAD'], cwd);
  return r.code === 0 ? r.stdout.trim() : null;
}

export async function isAncestor(cwd: string, a: string, b: string) {
  return (await run('git', ['merge-base', '--is-ancestor', a, b], cwd)).code === 0;
}

export async function operationInProgress(cwd: string): Promise<string | null> {
  const gitDir = (await run('git', ['rev-parse', '--git-dir'], cwd)).stdout.trim();
  const abs = path.resolve(cwd, gitDir);
  for (const f of ['CHERRY_PICK_HEAD', 'MERGE_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply']) {
    if (fs.existsSync(path.join(abs, f))) return f;
  }
  return null;
}
