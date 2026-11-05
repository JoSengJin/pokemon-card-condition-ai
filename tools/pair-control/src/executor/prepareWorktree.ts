import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import type { Executor, Check } from './executor.ts';
import type { PrepareInputT } from './prepareInput.ts';
import type { TaskInputT } from './contract.ts';

export function worktreeRoot(ex: Executor) {
  return ex.cfg.worktreeRoot || path.dirname(ex.cfg.repo);
}

async function branchExists(repo: string, branch: string) {
  return (await G.run('git', ['show-ref', '--verify', '--quiet', `refs/heads/${branch}`], repo)).code === 0;
}

export async function suggestTaskId(ex: Executor, agent: string) {
  const d = new Date();
  const stamp = `${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  for (let n = 1; n < 1000; n++) {
    const id = `task-${stamp}-${n}`;
    const exists = await G.run('git', ['show-ref', '--verify', '--quiet', `refs/heads/${agent}/${id}`], ex.cfg.repo);
    if (!ex.state.tasks[id] && exists.code !== 0) return id;
  }
  throw new Error('task ID 자동 생성 실패');
}

/** 재사용 가능한 이전 준비인지: 같은 브랜치의 등록된 worktree이고, 기준 SHA 이후 커밋은 이 task의 계약 파일만 바꿨으며 미커밋 변경이 없다. */
async function resumable(repo: string, worktree: string, branch: string, baseSha: string, taskId: string): Promise<true | string> {
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

/** git worktree add -b. 기존 경로·브랜치는 덮어쓰지 않는다(git 자체도 거절). */
export async function createWorktree(ex: Executor, t: TaskInputT) {
  if (fs.existsSync(t.worktree)) throw new Error(`이미 있는 경로: ${t.worktree}`);
  if (await branchExists(ex.cfg.repo, t.branch)) throw new Error(`이미 있는 브랜치: ${t.branch}`);
  fs.mkdirSync(path.dirname(t.worktree), { recursive: true });
  const r = await G.git(ex.cfg.repo, 'worktree', 'add', '-b', t.branch, t.worktree, t.baseSha);
  if (r.code !== 0) throw new Error(`git worktree add 실패: ${r.stderr.trim()}`);
  return fs.realpathSync.native(t.worktree);
}


export async function planWorktree(ex: Executor, input: PrepareInputT, taskId: string, baseSha: string, add: (name: string, ok: boolean, detail: string) => void): Promise<{ error: string } | { branch: string; worktree: string; createWorktree: boolean }> {
  const repo = ex.cfg.repo;
  // 브랜치·worktree
  let branch = `${input.agent}/${taskId}`;
  let worktree: string;
  let createWorktree: boolean;
  if (input.worktree) {
    createWorktree = false;
    const wts = await G.worktrees(repo);
    const real = fs.existsSync(input.worktree) ? fs.realpathSync.native(input.worktree) : input.worktree;
    const wt = wts.find((w) => w.path === real);
    if (!wt) return { error: '저장소의 git worktree 목록에 없는 경로' };
    if (wt.path === wts[0]?.path) return { error: '기본 checkout은 병렬 작업에 쓸 수 없음' };
    if (!wt.branch) return { error: 'detached HEAD — 작업 브랜치가 필요함' };
    worktree = wt.path; branch = wt.branch;
    add('worktree', true, `기존 worktree 사용 (${branch})`);
  } else {
    worktree = path.join(worktreeRoot(ex), `${path.basename(repo)}-${input.agent}-${taskId}`);
    const exists = fs.existsSync(worktree);
    const bExists = await branchExists(repo, branch);
    const resume = exists && bExists && !ex.state.tasks[taskId] ? await resumable(repo, worktree, branch, baseSha, taskId) : null;
    if (resume === true) {
      // 이전 준비가 등록 전에 멈춘 경우: 같은 worktree·브랜치를 재사용한다(중복 생성·중복 커밋 없음).
      createWorktree = false;
      worktree = fs.realpathSync.native(worktree);
      add('worktree', true, `이전 준비 재사용: ${worktree}`);
      add('브랜치', true, `이전 준비 재사용: ${branch}`);
    } else {
      createWorktree = true;
      add('worktree', !exists, exists ? `이미 있는 경로: ${worktree} (덮어쓰지 않음${typeof resume === 'string' ? ` — ${resume}` : ''})` : `새로 만듦: ${worktree}`);
      add('브랜치', !bExists, bExists ? `이미 있는 브랜치: ${branch} (덮어쓰지 않음)` : `새로 만듦: ${branch}`);
    }
  }

  return { branch, worktree, createWorktree };
}
