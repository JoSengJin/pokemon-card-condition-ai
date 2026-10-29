// Git 검사. 모든 호출은 execFile + 구조화된 인자이며 셸을 거치지 않는다.
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export interface Exec { code: number; stdout: string; stderr: string }

export function run(cmd: string, args: string[], cwd: string, timeoutMs = 60_000, env?: NodeJS.ProcessEnv): Promise<Exec> {
  return new Promise((resolve) => {
    execFile(cmd, args, { cwd, timeout: timeoutMs, maxBuffer: 32 * 1024 * 1024, env: env ?? process.env }, (err: any, stdout, stderr) => {
      resolve({ code: err ? (typeof err.code === 'number' ? err.code : 1) : 0, stdout: String(stdout), stderr: String(stderr) });
    });
  });
}

export const git = (cwd: string, ...args: string[]) => run('git', args, cwd);

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

/** 추적 파일 변경(staged/unstaged)과 untracked 파일. ignored 산출물은 제외한다. */
export async function dirtyFiles(cwd: string): Promise<string[]> {
  const r = await run('git', ['status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd);
  if (r.code !== 0) return ['<git status 실패>'];
  return r.stdout.split('\0').filter(Boolean).map((l) => l.slice(3));
}

export async function changedFiles(cwd: string, base: string, head: string): Promise<string[]> {
  const r = await run('git', ['diff', '--name-only', '-z', `${base}..${head}`], cwd);
  return r.stdout.split('\0').filter(Boolean);
}

export async function commitsBetween(cwd: string, base: string, head: string): Promise<string[]> {
  const r = await run('git', ['rev-list', '--reverse', `${base}..${head}`], cwd);
  return r.stdout.split('\n').map((s) => s.trim()).filter((s) => FULL_SHA.test(s));
}

export async function diffText(cwd: string, base: string, head: string, limit = 200_000) {
  const r = await run('git', ['diff', '--stat', '--patch', '--no-color', `${base}..${head}`], cwd);
  return r.stdout.length > limit ? r.stdout.slice(0, limit) + '\n… (잘림)' : r.stdout;
}

export async function operationInProgress(cwd: string): Promise<string | null> {
  const gitDir = (await run('git', ['rev-parse', '--git-dir'], cwd)).stdout.trim();
  const abs = path.resolve(cwd, gitDir);
  for (const f of ['CHERRY_PICK_HEAD', 'MERGE_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply']) {
    if (fs.existsSync(path.join(abs, f))) return f;
  }
  return null;
}
