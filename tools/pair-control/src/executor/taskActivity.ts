import * as G from './git.ts';
import { getTask } from './executorLookup.ts';
import { isAllowed } from './contract.ts';
import { tailFile } from './logstream.ts';
import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export function tailPostLog(ex: Executor, taskId: string, checkId: string, from: number) {
  const item = getTask(ex, taskId).integration?.postChecks?.find((i) => i.id === checkId);
  if (!item?.logPath) throw new UserError('통합 후 검사 로그 없음');
  return tailFile(item.logPath, Math.max(0, from));
}

export async function activityOf(ex: Executor, taskId: string) {
  const t = getTask(ex, taskId);
  const base = t.contractSha || t.baseSha; // 계약 커밋 위의 작업만(Git 계약 검사와 같은 기준)
  const log = await G.git(t.worktree, 'log', '--format=%h%x09%cI%x09%s', `${base}..HEAD`);
  const commits = log.stdout.split('\n').filter(Boolean).slice(0, 30).map((l) => { const [sha, at, ...s] = l.split('\t'); return { sha, at, subject: s.join('\t') }; });
  const changed = await G.changedFiles(t.worktree, base, 'HEAD');
  const dirty = await G.dirtyFiles(t.worktree);
  const all = [...new Set([...changed, ...dirty])];
  return { commits, changed: changed.slice(0, 100), dirty: dirty.slice(0, 100), outOfScope: all.filter((f) => !isAllowed(f, t.allowedFiles)).slice(0, 100), at: new Date().toISOString() };
}
