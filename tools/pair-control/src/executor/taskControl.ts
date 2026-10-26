// 작업 제어: 승인 취소(승인됨 → 검토 단계), 작업 보관(목록에서 숨기기), 실행 환경 만들기(.venv). 에이전트를 다시 실행하지 않는다.
import fs from 'node:fs';
import { isAllowed } from './contract.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import * as G from './git.ts';
import { tailFile } from './logstream.ts';
import { appendEvent } from './store.ts';
import { OCCUPYING, UserError, type Executor, type Task } from './executor.ts';

type Resume = (runId: string, step: string, data: Record<string, unknown>) => Promise<unknown>;

function record(ex: Executor, t: Task, type: string, data: Record<string, unknown> = {}) {
  t.updatedAt = new Date().toISOString();
  appendEvent(ex.cfg.stateDir, { type, lifetime: ex.lifetime, taskId: t.taskId, ...data });
  ex.store.save();
}

/**
 * 승인을 취소하고 같은 SHA로 검토 단계로 되돌린다. 통합 전이라 통합 브랜치는 바뀌지 않는다.
 * 기존 workflow 실행은 integrate-gate에서 withdraw로 끝내고, 재검토(reviewOnly) 실행으로 결과를 다시 수집한다.
 * 같은 SHA·계약의 작업 테스트·리뷰·인계 기록은 그대로 유효하다.
 */
export async function withdrawApproval(ex: Executor, taskId: string, resume: Resume, rereview: (taskId: string) => Promise<unknown>) {
  const t = ex.task(taskId);
  if (!['approved', 'integration_blocked'].includes(t.status) || !t.approval) throw new UserError(`승인 취소는 승인됨 상태에서만 가능(${t.status})`);
  const sha = t.approval.sha, oldRun = t.runId;
  t.approval = null;
  t.status = 'integration_refused';
  t.statusReason = '사용자가 승인을 취소 — 같은 SHA로 검토 단계로 되돌리는 중';
  record(ex, t, 'approval_withdrawn', { sha, runId: oldRun, status: t.status });
  if (oldRun) {
    try { await resume(oldRun, 'integrate-gate', { action: 'withdraw' }); }
    catch (err) { record(ex, t, 'resume_error', { runId: oldRun, error: (err as Error).message }); }
  }
  await rereview(taskId);
  return ex.task(taskId);
}

/** 끝났거나 시작 전인 작업만 목록에서 숨긴다. 기록·worktree·브랜치는 그대로 두고 언제든 해제할 수 있다. */
export function setArchived(ex: Executor, taskId: string, archived: boolean) {
  const t = ex.task(taskId);
  if (archived && OCCUPYING.includes(t.status)) throw new UserError(`진행 중이거나 결정이 남은 작업은 보관할 수 없음(${t.status}) — 먼저 취소·거절하거나 통합하세요`);
  t.archivedAt = archived ? new Date().toISOString() : null;
  record(ex, t, archived ? 'task_archived' : 'task_unarchived');
  return t;
}

const BEFORE_START = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

/**
 * 이 작업의 worktree에 자체 .venv를 만든다. 고정 명령 `python3 -m venv .venv` 하나뿐이다: 셸 없음, 패키지 설치 없음, 네트워크 없음.
 * 기본 checkout·등록되지 않은 폴더·진행 중 작업·이미 있는 .venv(링크 포함)는 거부한다. 끝나면 실행 준비를 다시 확인한다.
 */
export async function createVenv(ex: Executor, taskId: string) {
  const t = ex.task(taskId);
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
  return ex.recheckEnv(taskId);
}

/** 통합 후 검사 항목의 로그를 이어서 읽는다. 파일은 작업 상태에 기록된 항목에서만 찾는다(클라이언트가 경로를 주지 않음). */
export function tailPostLog(ex: Executor, taskId: string, checkId: string, from: number) {
  const item = ex.task(taskId).integration?.postChecks?.find((i) => i.id === checkId);
  if (!item?.logPath) throw new UserError('통합 후 검사 로그 없음');
  return tailFile(item.logPath, Math.max(0, from));
}

/**
 * 수동 모드처럼 볼 출력이 없는 작업의 활동: 작업 폴더의 새 커밋, 변경 파일(커밋됨·미커밋), 허용 범위 밖 변경.
 * 읽기만 한다(git log/status). 숫자와 목록은 화면이 그대로 보여 주며 판정에는 쓰이지 않는다.
 */
export async function activityOf(ex: Executor, taskId: string) {
  const t = ex.task(taskId);
  const base = t.contractSha || t.baseSha; // 계약 커밋 위의 작업만(Git 계약 검사와 같은 기준)
  const log = await G.git(t.worktree, 'log', '--format=%h%x09%cI%x09%s', `${base}..HEAD`);
  const commits = log.stdout.split('\n').filter(Boolean).slice(0, 30).map((l) => { const [sha, at, ...s] = l.split('\t'); return { sha, at, subject: s.join('\t') }; });
  const changed = await G.changedFiles(t.worktree, base, 'HEAD');
  const dirty = await G.dirtyFiles(t.worktree);
  const all = [...new Set([...changed, ...dirty])];
  return { commits, changed: changed.slice(0, 100), dirty: dirty.slice(0, 100), outOfScope: all.filter((f) => !isAllowed(f, t.allowedFiles)).slice(0, 100), at: new Date().toISOString() };
}
