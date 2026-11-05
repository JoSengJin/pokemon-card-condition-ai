import { run } from './gitProcess.ts';

export async function dirtyFiles(cwd: string): Promise<string[]> {
  const r = await run('git', ['status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd);
  return parseDirtyFiles(r);
}

export async function changedFiles(cwd: string, base: string, head: string): Promise<string[]> {
  const r = await run('git', ['diff', '--name-only', '-z', `${base}..${head}`], cwd);
  return r.stdout.split('\0').filter(Boolean);
}

export async function diffText(cwd: string, base: string, head: string, limit = 200_000) {
  const r = await run('git', ['diff', '--stat', '--patch', '--no-color', `${base}..${head}`], cwd);
  return r.stdout.length > limit ? r.stdout.slice(0, limit) + '\n… (잘림)' : r.stdout;
}

export function parseDirtyFiles(result: { code: number; stdout: string }): string[] {
  if (result.code !== 0) return ['<git status 실패>'];
  const files = [];
  for (const line of result.stdout.split('\0')) if (line) files.push(line.slice(3));
  return files;
}
