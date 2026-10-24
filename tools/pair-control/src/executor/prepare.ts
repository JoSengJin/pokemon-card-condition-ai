// 작업 준비 자동화: 사람은 담당·목표·허용 파일만 고르고, 브랜치·기준 SHA·worktree 경로는 결정적으로 계산한다.
// 미리보기(planTask)는 부작용이 없고, 생성(createWorktree)은 사용자가 배정을 누를 때 Mastra prepare-task workflow 안에서만 실행된다.
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import * as G from './git.ts';
import { AGENTS, MODES, MOCK_SCENARIOS, conflicts, isAllowed, isForbidden, TaskInput, type ConflictReason, type TaskInputT } from './contract.ts';
import { OCCUPYING, type Check, type Executor } from './executor.ts';

export const PrepareInput = z.object({
  taskId: z.string().trim().optional().default(''),
  agent: z.enum(AGENTS),
  mode: z.enum(MODES).default('mock'),
  mockScenario: z.enum(MOCK_SCENARIOS).default('success'),
  goal: z.string().trim().min(1, '목표를 적어 주세요').max(500),
  prompt: z.string().max(8000).default(''),
  allowedFiles: z.array(z.string()).default([]),
  conflictGroups: z.array(z.string()).default([]),
  doneCriteria: z.array(z.string()).default([]),
  /** 구조화된 검사 명령. 상세 검증은 TaskInput(CheckSpec)이 한다. */
  checks: z.array(z.any()).default([]),
  postChecks: z.array(z.any()).default([]),
  env: z.enum(['auto', 'none', 'python', 'python-project']).default('auto'),
  requiredModules: z.array(z.string()).default([]),
  /** 고급: 기준 SHA 직접 지정(비우면 통합 브랜치 HEAD) */
  baseSha: z.string().trim().optional().default(''),
  /** 고급: 이미 있는 worktree 사용(비우면 새로 만든다) */
  worktree: z.string().trim().optional().default(''),
});
export type PrepareInputT = z.infer<typeof PrepareInput>;

export interface Plan {
  ok: boolean;
  task: TaskInputT | null;
  createWorktree: boolean;
  baseRef: string;
  baseSubject: string;
  checks: Check[];
  conflicts: ConflictReason[];
  warnings: string[];
  envAuto?: boolean;
}


export function worktreeRoot(ex: Executor) {
  return ex.cfg.worktreeRoot || path.dirname(ex.cfg.repo);
}

async function branchExists(repo: string, branch: string) {
  return (await G.git(repo, 'show-ref', '--verify', '--quiet', `refs/heads/${branch}`)).code === 0;
}

async function suggestTaskId(ex: Executor, agent: string) {
  const d = new Date();
  const stamp = `${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  for (let n = 1; n < 1000; n++) {
    const id = `task-${stamp}-${n}`;
    if (!ex.state.tasks[id] && !(await branchExists(ex.cfg.repo, `${agent}/${id}`))) return id;
  }
  throw new Error('task ID 자동 생성 실패');
}

export async function planTask(ex: Executor, raw: unknown): Promise<Plan> {
  const checks: Check[] = [];
  const warnings: string[] = [];
  const add = (name: string, ok: boolean, detail: string) => checks.push({ name, ok, detail });
  const fail = (name: string, detail: string): Plan => { add(name, false, detail); return { ok: false, task: null, createWorktree: false, baseRef: '', baseSubject: '', checks, conflicts: [], warnings }; };

  const p = PrepareInput.safeParse(raw);
  if (!p.success) return fail('입력', p.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
  const input = p.data;
  const repo = ex.cfg.repo;
  if (!repo) return fail('설정', 'config.repo 미설정');

  // task ID
  const taskId = input.taskId || (await suggestTaskId(ex, input.agent));
  add('task ID', !ex.state.tasks[taskId], input.taskId ? taskId : `${taskId} (자동 생성)`);

  // 기준 SHA: 기본은 통합 브랜치 HEAD
  const baseRef = input.baseSha ? '직접 지정' : `${ex.cfg.integration.branch} 최신`;
  const baseSha = input.baseSha
    ? (G.FULL_SHA.test(input.baseSha) ? await G.revParse(repo, input.baseSha) : null)
    : await G.revParse(repo, `refs/heads/${ex.cfg.integration.branch}`);
  if (!baseSha) return fail('기준 SHA', input.baseSha ? '40자 커밋 SHA가 아니거나 저장소에 없음' : `${ex.cfg.integration.branch} 브랜치를 읽지 못함`);
  const baseSubject = (await G.git(repo, 'log', '-1', '--format=%s (%cr)', baseSha)).stdout.trim();
  add('기준 SHA', true, `${baseSha.slice(0, 12)} · ${baseRef} · ${baseSubject}`);

  // 브랜치·worktree
  let branch = `${input.agent}/${taskId}`;
  let worktree: string;
  let createWorktree: boolean;
  if (input.worktree) {
    createWorktree = false;
    const wts = await G.worktrees(repo);
    const real = fs.existsSync(input.worktree) ? fs.realpathSync.native(input.worktree) : input.worktree;
    const wt = wts.find((w) => w.path === real);
    if (!wt) return fail('기존 worktree', '저장소의 git worktree 목록에 없는 경로');
    if (wt.path === wts[0]?.path) return fail('기존 worktree', '기본 checkout은 병렬 작업에 쓸 수 없음');
    if (!wt.branch) return fail('기존 worktree', 'detached HEAD — 작업 브랜치가 필요함');
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

  // 허용 파일
  if (!input.allowedFiles.length) add('허용 파일', false, '고칠 파일·폴더를 하나 이상 고르세요');
  const tracked = await listTracked(repo, baseSha);
  const missing = input.allowedFiles.filter((f) => !(f.endsWith('/') ? tracked.dirs.has(f) : tracked.files.has(f)));
  if (missing.length) warnings.push(`기준 커밋에 없는 경로(새 파일로 간주): ${missing.join(', ')}`);

  // 실행 환경 자동 판단: Python 파일·모델 경로·.venv 검사가 있으면 자체 가상환경이 필요하다.
  const envAuto = input.env === 'auto';
  const usesPython = input.allowedFiles.some((f) => f.endsWith('.py') || /^(card_condition|tests|tools\/experiments)(\/|$)/.test(f))
    || [...input.checks, ...input.postChecks].some((c: any) => c?.executable === '.venv/bin/python');
  const envProfile = envAuto ? (usesPython ? 'python' : 'none') : input.env;
  const task = { taskId, agent: input.agent, mode: input.mode, mockScenario: input.mockScenario, branch, worktree, baseSha,
    allowedFiles: input.allowedFiles, conflictGroups: input.conflictGroups, goal: input.goal, prompt: input.prompt,
    doneCriteria: input.doneCriteria, checks: input.checks, postChecks: input.postChecks, env: envProfile, requiredModules: input.requiredModules };
  const v = TaskInput.safeParse(task);
  if (!v.success) add('계약 규칙', false, v.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
  else add('계약 규칙', true, '금지 경로·브랜치 접두어·검사 명령 형식 통과');
  if (v.success && !v.data.checks.length) warnings.push('작업 테스트가 없으면 승인할 수 없음(미실행은 통과가 아님)');

  // 진행 중 작업과의 겹침(배정은 가능, 시작은 그 작업이 끝날 때까지 거절)
  const found: ConflictReason[] = [];
  if (v.success) {
    for (const o of Object.values(ex.state.tasks)) {
      if (OCCUPYING.includes(o.status)) found.push(...conflicts(v.data, o));
    }
  }
  if (found.length) warnings.push(`진행 중 작업과 겹침 → 그 작업이 통합/거절될 때까지 시작 불가: ${[...new Set(found.map((c) => `${c.otherTask}(${c.detail})`))].join(', ')}`);
  if (ex.guardAlert) add('무료 가드', false, `발동됨: ${ex.guardAlert.detail}`);

  const ok = checks.every((c) => c.ok);
  return { ok, task: v.success ? v.data : null, createWorktree, baseRef, baseSubject, checks, conflicts: found, warnings, envAuto };
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

/** 기준 커밋의 추적 파일·폴더 목록(파일 선택 화면용). */
export async function listTracked(repo: string, ref: string) {
  const r = await G.git(repo, 'ls-tree', '-r', '-t', '-z', ref);
  const files = new Set<string>(), dirs = new Set<string>();
  for (const entry of r.stdout.split('\0')) {
    const tab = entry.indexOf('\t');
    if (tab < 0) continue;
    const type = entry.slice(0, tab).split(' ')[1];
    const p = entry.slice(tab + 1);
    if (type === 'tree') dirs.add(`${p}/`); else if (type === 'blob') files.add(p);
  }
  return { files, dirs };
}

/** 파일 선택 화면용: 경로 목록 + 진행 중 작업이 쓰는 경로 표시. */
export async function fileChoices(ex: Executor) {
  const repo = ex.cfg.repo;
  const base = await G.revParse(repo, `refs/heads/${ex.cfg.integration.branch}`);
  if (!base) return { base: null, entries: [] };
  const { files, dirs } = await listTracked(repo, base);
  const busy = Object.values(ex.state.tasks).filter((t) => OCCUPYING.includes(t.status));
  const entries = [...dirs, ...files].sort().map((p) => {
    const owners = busy.filter((t) => t.allowedFiles.some((a) => isAllowed(p, [a]) || isAllowed(a, [p]))).map((t) => t.taskId);
    return { path: p, dir: p.endsWith('/'), owners, forbidden: isForbidden(p) };
  });
  return { base, entries };
}
