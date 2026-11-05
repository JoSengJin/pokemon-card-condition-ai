import { run } from './gitProcess.ts';
import { FULL_SHA } from './gitRefs.ts';

export async function commitsBetween(cwd: string, base: string, head: string): Promise<string[]> {
  const r = await run('git', ['rev-list', '--reverse', `${base}..${head}`], cwd);
  return r.stdout.split('\n').map((s) => s.trim()).filter((s) => FULL_SHA.test(s));
}
