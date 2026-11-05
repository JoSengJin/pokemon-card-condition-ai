import { run } from './gitProcess.ts';

export async function dirtyFiles(cwd: string): Promise<string[]> {
  const r = await run('git', ['status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd);
  if (r.code !== 0) return ['<git status 실패>'];
  return r.stdout.split('\0').filter(Boolean).map((l) => l.slice(3));
}

export async function changedFiles(cwd: string, base: string, head: string): Promise<string[]> {
  const r = await run('git', ['diff', '--name-only', '-z', `${base}..${head}`], cwd);
  return r.stdout.split('\0').filter(Boolean);
}

export async function diffText(cwd: string, base: string, head: string, limit = 200_000) {
  const r = await run('git', ['diff', '--stat', '--patch', '--no-color', `${base}..${head}`], cwd);
  return r.stdout.length > limit ? r.stdout.slice(0, limit) + '\n… (잘림)' : r.stdout;
}
