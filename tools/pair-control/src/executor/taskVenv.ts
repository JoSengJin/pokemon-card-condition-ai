import fs from 'node:fs';
import * as G from './git.ts';
import { getTask } from './executorLookup.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { recheckEnv } from './taskEnvironment.ts';
import { record } from './taskControlRecord.ts';
import { UserError } from './errors.ts';
import type { Executor } from './executor.ts';

export const BEFORE_START = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export async function createVenv(ex: Executor, taskId: string) {
  const t = getTask(ex, taskId);
  if (!BEFORE_START.includes(t.status)) throw new UserError(`시작 전·중단된 작업에서만 환경을 만들 수 있음(${t.status})`);
  const wts = await G.worktrees(ex.cfg.repo);
  const real = fs.existsSync(t.worktree) ? fs.realpathSync.native(t.worktree) : t.worktree;
  if (!wts.some((w) => w.path === real)) throw new UserError('저장소의 git worktree 목록에 없는 폴더');
  if (real === wts[0]?.path) throw new UserError('기본 checkout에는 환경을 만들지 않음');
  const venv = `${real}/.venv`;
  try { fs.lstatSync(venv); throw new UserError('이미 .venv가 있음 — 지우고 다시 만들려면 직접 처리하세요(도구는 지우지 않음)'); }
  catch (err) { if (err instanceof UserError) throw err; }
  const r = await G.run('python3', ['-m', 'venv', '.venv'], real, 180_000, sanitizedChildEnv());
  record(ex, t, 'venv_created', { code: r.code, stderr: r.stderr.slice(0, 300) });
  if (r.code !== 0) throw new UserError(`python3 -m venv 실패(code ${r.code}): ${r.stderr.trim().slice(0, 300)}`);
  return recheckEnv(ex, taskId);
}
