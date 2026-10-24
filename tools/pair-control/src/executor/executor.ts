// Node 실행기: 작업 소유권·CLI 프로세스·Git 검사·취소·상태 저장·통합.
// Mastra workflow는 단계·승인 대기를 맡고, 실제 프로세스와 Git 상태의 근거는 이 실행기가 가진다.
import { spawn, execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import type { PairConfig } from './config.ts';
import { appendEvent, Store, writeJsonAtomic } from './store.ts';
import { LockDir } from './locks.ts';
import * as G from './git.ts';
import { conflicts, effectiveGroups, isAllowed, needsDevelopLock, TaskInput, type ConflictReason, type TaskInputT } from './contract.ts';
import { mockPlan, probe, realPlan, type LaunchPlan, type Probe } from './adapters.ts';
import { FreeGuard, sanitizedChildEnv, type Alert } from './freeGuard.ts';

export type TaskStatus =
  | 'assigned' | 'blocked' | 'starting' | 'running' | 'collecting' | 'cancelling' | 'cancelled' | 'failed'
  | 'orphan_running' | 'exit_observed' | 'unknown' | 'abandoned'
  | 'review_pending' | 'approved' | 'rejected'
  | 'integrating' | 'integrated' | 'integration_refused' | 'integration_conflict' | 'integration_blocked';

/** 실행 잠금은 없어도 같은 파일의 결과가 아직 통합/거절되지 않은 상태. */
export const OCCUPYING: TaskStatus[] = ['starting', 'running', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
  'review_pending', 'approved', 'integrating', 'integration_refused', 'integration_conflict', 'integration_blocked'];
const STARTABLE: TaskStatus[] = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export interface Check { name: string; ok: boolean; detail: string }

export interface Approval { sha: string; baseBranch: string; baseHead: string; files: string[]; filesHash: string; at: string }

export interface Task extends TaskInputT {
  status: TaskStatus;
  statusReason?: string;
  createdAt: string;
  updatedAt: string;
  runId?: string | null;
  runHistory: string[];
  lastExecId?: string | null;
  preflight?: Check[];
  permission?: string;
  usesDevelopLock: boolean;
  result?: {
    execId: string | null; headSha: string | null; commits: string[]; changedFiles: string[]; dirtyFiles: string[];
    outOfScope: string[]; checks: Check[]; checksPassed: boolean; collectedAt: string;
  } | null;
  approval?: Approval | null;
  integration?: { at: string; outcome: string; detail: string; newHead?: string | null; conflictFiles?: string[]; commits?: string[] } | null;
}

export type ExecStatus = 'running' | 'cancelling' | 'exited' | 'cancelled' | 'unknown' | 'abandoned';
export interface Execution {
  execId: string; taskId: string; runId: string; token: string; agent: string; mode: string; display: string[];
  pid: number; pgid: number; startedAt: string; endedAt?: string; status: ExecStatus;
  exitCode?: number | null; signal?: string | null; spawnError?: string | null; cancelRequested: boolean;
  observedAfterRestart: boolean; serverLifetime: string; logPath: string; exitPath: string; specPath: string;
  tokens: '미측정'; cost: '미측정';
}

interface State { tasks: Record<string, Task>; executions: Record<string, Execution> }

export type Resumer = (runId: string, step: string, data: Record<string, unknown>) => Promise<void>;

export class Executor {
  readonly store: Store<State>;
  readonly locks: LockDir;
  readonly guard: FreeGuard;
  readonly lifetime = crypto.randomUUID();
  readonly probes: Partial<Record<'codex' | 'claude', Probe>> = {};
  private timer: NodeJS.Timeout | null = null;
  private logOffsets = new Map<string, number>();
  private resumer: Resumer | null = null;
  private tripped: Alert | null = null;
  private ticking = false;

  constructor(readonly cfg: PairConfig, opts: { onTrip?: (a: Alert) => void } = {}) {
    fs.mkdirSync(cfg.stateDir, { recursive: true });
    this.store = new Store<State>(path.join(cfg.stateDir, 'state.json'), { tasks: {}, executions: {} });
    this.locks = new LockDir(path.join(cfg.stateDir, 'locks'));
    this.guard = new FreeGuard(cfg.stateDir, (a) => {
      this.tripped = a;
      this.event('free_guard_trip', { ...a });
      this.cancelAll('무료 가드 발동');
      opts.onTrip?.(a);
    });
    this.tripped = this.guard.pending();
    this.recover();
  }

  get state() { return this.store.data; }
  setResumer(r: Resumer) { this.resumer = r; }
  get supervisorPath() { return path.join(this.cfg.toolRoot, 'src', 'executor', 'supervisor.mjs'); }
  get guardAlert() { return this.tripped; }

  private event(type: string, data: Record<string, unknown>) { appendEvent(this.cfg.stateDir, { type, lifetime: this.lifetime, ...data }); }
  private save() { this.store.save(); }
  private setStatus(t: Task, s: TaskStatus, reason?: string) {
    t.status = s; t.statusReason = reason; t.updatedAt = new Date().toISOString();
    this.event('task_status', { taskId: t.taskId, status: s, reason });
    this.save();
  }

  task(id: string) {
    const t = this.state.tasks[id];
    if (!t) throw new UserError(`task 없음: ${id}`);
    return t;
  }

  // ---------- 배정 ----------
  async assign(raw: unknown): Promise<Task> {
    const parsed = TaskInput.safeParse(raw);
    if (!parsed.success) throw new UserError(parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
    const input = parsed.data;
    if (this.state.tasks[input.taskId]) throw new UserError(`이미 배정된 task ID: ${input.taskId}`);
    const worktree = fs.existsSync(input.worktree) ? fs.realpathSync.native(input.worktree) : input.worktree;
    const now = new Date().toISOString();
    const t: Task = { ...input, worktree, status: 'assigned', createdAt: now, updatedAt: now, runHistory: [], usesDevelopLock: needsDevelopLock(input) };
    t.preflight = await this.preflightChecks(t);
    this.state.tasks[t.taskId] = t;
    this.event('task_assigned', { taskId: t.taskId, agent: t.agent, mode: t.mode, branch: t.branch, baseSha: t.baseSha });
    this.save();
    return t;
  }

  // ---------- 사전 검사 ----------
  async preflightChecks(t: Task): Promise<Check[]> {
    const c: Check[] = [];
    const add = (name: string, ok: boolean, detail: string) => c.push({ name, ok, detail });
    if (!this.cfg.repo) { add('설정', false, 'config.repo 미설정'); return c; }
    const wts = await G.worktrees(this.cfg.repo);
    const main = wts[0]?.path;
    const integ = this.cfg.integration.checkout && fs.existsSync(this.cfg.integration.checkout) ? fs.realpathSync.native(this.cfg.integration.checkout) : null;
    const wt = wts.find((w) => w.path === t.worktree);
    add('worktree 등록', !!wt, wt ? '저장소 worktree 목록에 있음' : '저장소의 git worktree 목록에 없는 경로');
    add('기본 checkout 분리', t.worktree !== main && t.worktree !== integ, t.worktree === main || t.worktree === integ ? '기본/통합 checkout에서는 병렬 작업을 실행하지 않음' : '별도 worktree');
    if (!wt) return c;
    const branch = await G.currentBranch(t.worktree);
    add('브랜치', branch === t.branch, `현재 ${branch ?? '(detached)'} / 계약 ${t.branch}`);
    const baseOk = !!(await G.revParse(t.worktree, t.baseSha)) && (await G.isAncestor(t.worktree, t.baseSha, 'HEAD'));
    add('기준 SHA', baseOk, baseOk ? `${t.baseSha.slice(0, 12)}…는 HEAD의 조상` : '기준 SHA가 없거나 HEAD의 조상이 아님');
    const op = await G.operationInProgress(t.worktree);
    add('Git 진행 중 작업 없음', !op, op ?? '없음');
    const venv = path.join(t.worktree, '.venv');
    const venvLink = fs.existsSync(venv) && fs.lstatSync(venv).isSymbolicLink();
    add('가상환경 분리', !venvLink, venvLink ? '.venv가 심볼릭 링크(공유 금지)' : fs.existsSync(venv) ? '자체 .venv 있음' : '.venv 없음(mock은 불필요, 실제 Python 검사 전 생성 필요)');
    if (t.usesDevelopLock) {
      const dev = path.join(t.worktree, 'develop');
      let ok = false; try { fs.accessSync(dev, fs.constants.X_OK); ok = true; } catch { /* missing */ }
      add('./develop 잠금 경로', ok, ok ? '모델·worker 경로 → worktree의 ./develop -- <CLI> 로 실행' : 'worktree에 실행 가능한 ./develop 없음');
    }
    add('무료 가드', !this.tripped, this.tripped ? `발동됨: ${this.tripped.detail}` : '정상');
    return c;
  }

  // ---------- 시작 ----------
  /** 동기 구간에서 충돌 검사와 잠금 획득을 함께 수행한다(같은 프로세스 내 원자성). 파일 잠금은 프로세스 간 중복을 막는다. */
  private reserve(t: Task, execId: string): { ok: true } | { ok: false; reason: string; conflicts?: ConflictReason[] } {
    if (this.tripped) return { ok: false, reason: `무료 가드 발동 상태: ${this.tripped.detail}` };
    if (!STARTABLE.includes(t.status)) return { ok: false, reason: `현재 상태(${t.status})에서는 시작할 수 없음(중복 실행 차단)` };
    const found: ConflictReason[] = [];
    for (const o of Object.values(this.state.tasks)) {
      if (o.taskId === t.taskId || !OCCUPYING.includes(o.status)) continue;
      found.push(...conflicts(t, o));
    }
    if (found.length) return { ok: false, reason: '다른 진행 중 작업과 충돌', conflicts: found };
    const names = [`task:${t.taskId}`, `worktree:${t.worktree}`, `branch:${t.branch}`];
    const got: string[] = [];
    for (const n of names) {
      if (!this.locks.acquire(n, { execId, taskId: t.taskId, lifetime: this.lifetime })) {
        for (const g of got) this.locks.release(g, 'execId', execId);
        return { ok: false, reason: `잠금 사용 중: ${n} (소유 ${JSON.stringify(this.locks.holder(n))})` };
      }
      got.push(n);
    }
    this.setStatus(t, 'starting');
    return { ok: true };
  }

  private releaseExecLocks(t: Task, execId: string) {
    for (const n of [`task:${t.taskId}`, `worktree:${t.worktree}`, `branch:${t.branch}`]) this.locks.release(n, 'execId', execId);
  }

  async launch(taskId: string, runId: string): Promise<{ ok: true; execId: string; pid: number } | { ok: false; reason: string; conflicts?: ConflictReason[]; checks?: Check[] }> {
    const t = this.task(taskId);
    const execId = crypto.randomUUID();
    const r = this.reserve(t, execId);
    if (!r.ok) {
      const reason = r.conflicts?.length ? `${r.reason}: ${r.conflicts.map((c) => `${c.otherTask}(${c.kind} ${c.detail})`).join(', ')}` : r.reason;
      this.event('start_refused', { taskId, reason });
      // 실행 중 작업의 중복 시작이면 상태를 건드리지 않고, 시작 가능한 작업이면 거절 사유만 남긴다.
      if (STARTABLE.includes(t.status)) { t.statusReason = `시작 거절: ${reason}`; t.updatedAt = new Date().toISOString(); this.save(); }
      return { ...r, reason };
    }
    try {
      const checks = await this.preflightChecks(t);
      t.preflight = checks;
      const failed = checks.filter((c) => !c.ok);
      let plan: LaunchPlan | { refused: string };
      if (t.mode === 'mock') plan = mockPlan(t, this.cfg);
      else {
        this.probes[t.agent] = await probe(t.agent, this.cfg);
        plan = realPlan(t, this.probes[t.agent]!, this.cfg);
      }
      if (failed.length || 'refused' in plan) {
        const reason = failed.length ? `사전 검사 실패: ${failed.map((c) => `${c.name}(${c.detail})`).join(', ')}` : (plan as { refused: string }).refused;
        this.releaseExecLocks(t, execId);
        this.setStatus(t, 'blocked', reason);
        return { ok: false, reason, checks };
      }
      t.permission = plan.permission;
      return this.spawnExec(t, runId, execId, plan);
    } catch (err) {
      this.releaseExecLocks(t, execId);
      this.setStatus(t, 'blocked', `시작 오류: ${(err as Error).message}`);
      return { ok: false, reason: (err as Error).message };
    }
  }

  private spawnExec(t: Task, runId: string, execId: string, plan: LaunchPlan) {
    const dir = path.join(this.cfg.stateDir, 'runs', execId);
    fs.mkdirSync(dir, { recursive: true });
    const token = crypto.randomUUID();
    let command = plan.command, args = plan.args;
    if (t.mode === 'mock') args = [...args, '--counter', path.join(this.cfg.stateDir, 'mock-invocations.jsonl')];
    if (t.usesDevelopLock) { command = path.join(t.worktree, 'develop'); args = ['--', plan.command, ...args]; }
    const spec = { execId, token, cwd: t.worktree, command, args, env: sanitizedChildEnv(), logPath: path.join(dir, 'output.log'), exitPath: path.join(dir, 'exit.json') };
    const specPath = path.join(dir, 'spec.json');
    writeJsonAtomic(specPath, spec);
    fs.writeFileSync(spec.logPath, '');
    const sup = spawn(process.execPath, [this.supervisorPath, specPath], { cwd: t.worktree, detached: true, stdio: 'ignore', env: sanitizedChildEnv() });
    sup.unref();
    if (!sup.pid) throw new Error('감독 프로세스 시작 실패');
    const ex: Execution = {
      execId, taskId: t.taskId, runId, token, agent: t.agent, mode: t.mode, display: t.usesDevelopLock ? ['./develop', '--', ...plan.display] : plan.display,
      pid: sup.pid, pgid: sup.pid, startedAt: new Date().toISOString(), status: 'running', cancelRequested: false,
      observedAfterRestart: false, serverLifetime: this.lifetime, logPath: spec.logPath, exitPath: spec.exitPath, specPath,
      tokens: '미측정', cost: '미측정',
    };
    this.state.executions[execId] = ex;
    t.lastExecId = execId; t.runId = runId; t.runHistory = [...t.runHistory, runId]; t.result = null; t.approval = null; t.integration = null;
    this.setStatus(t, 'running');
    this.event('exec_started', { taskId: t.taskId, execId, runId, pid: ex.pid, display: ex.display });
    this.ensureWatcher();
    return { ok: true as const, execId, pid: ex.pid };
  }

  // ---------- 감시 ----------
  ensureWatcher() {
    if (!this.timer) { this.timer = setInterval(() => void this.tick(), 300); this.timer.unref?.(); }
  }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }

  private alive(pid: number) { try { process.kill(pid, 0); return true; } catch (e: any) { return e.code === 'EPERM'; } }
  groupAlive(pgid: number) { try { process.kill(-pgid, 0); return true; } catch (e: any) { return e.code === 'EPERM'; } }

  /** 감독 프로세스가 이 실행기의 spec으로 실행된 프로세스인지(PID 재사용 방지). */
  private ownsLeader(ex: Execution): boolean | null {
    try {
      const out = execFileSync('ps', ['-o', 'pgid=,command=', '-p', String(ex.pid)]).toString().trim();
      if (!out) return null;
      const [pgid, ...cmd] = out.split(/\s+/);
      return Number(pgid) === ex.pgid && cmd.join(' ').includes(ex.specPath);
    } catch { return null; }
  }

  private readNewLog(ex: Execution) {
    const off = this.logOffsets.get(ex.execId) ?? 0;
    try {
      const size = fs.statSync(ex.logPath).size;
      if (size <= off) return;
      const fd = fs.openSync(ex.logPath, 'r');
      const buf = Buffer.alloc(Math.min(size - off, 1_000_000));
      fs.readSync(fd, buf, 0, buf.length, off); fs.closeSync(fd);
      this.logOffsets.set(ex.execId, off + buf.length);
      this.guard.scanLog(buf.toString(), `exec:${ex.execId}`);
    } catch { /* log not yet created */ }
  }

  async tick() {
    if (this.ticking) return;
    this.ticking = true;
    try { await this.tickOnce(); } finally { this.ticking = false; }
  }

  private async tickOnce() {
    for (const ex of Object.values(this.state.executions)) {
      if (ex.status !== 'running' && ex.status !== 'cancelling') continue;
      this.readNewLog(ex);
      if (fs.existsSync(ex.exitPath)) { await this.finalize(ex); continue; }
      if (!this.alive(ex.pid)) {
        await new Promise((r) => setTimeout(r, 200));
        if (fs.existsSync(ex.exitPath)) { await this.finalize(ex); continue; }
        if (this.groupAlive(ex.pgid)) continue; // 리더만 죽고 자식이 남은 경우: 정리 전까지 실행 중으로 본다
        const t = this.state.tasks[ex.taskId];
        if (ex.cancelRequested) {
          ex.status = 'cancelled'; ex.endedAt = new Date().toISOString();
          this.releaseExecLocks(t, ex.execId);
          this.setStatus(t, 'collecting', '사용자 중단(강제 종료로 종료 기록 없음) · 결과 수집 중');
          await this.resume(t, ex, { execId: ex.execId, exitCode: null, signal: 'SIGKILL', cancelled: true });
        } else {
          ex.status = 'unknown';
          this.setStatus(t, 'unknown', '감독 프로세스가 종료 기록 없이 사라짐(결과 불명). 잠금 유지.');
        }
      }
    }
  }

  private async finalize(ex: Execution) {
    const t = this.state.tasks[ex.taskId];
    let res: any = {};
    try { res = JSON.parse(fs.readFileSync(ex.exitPath, 'utf8')); } catch { return; }
    if (res.token !== ex.token) { ex.status = 'unknown'; this.setStatus(t, 'unknown', 'exit.json 토큰 불일치'); return; }
    this.readNewLog(ex);
    if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } // 남은 손자 정리
    const cancelled = ex.cancelRequested || res.cancelRequested;
    ex.exitCode = res.code; ex.signal = res.signal; ex.spawnError = res.spawnError ?? null; ex.endedAt = res.endedAt;
    ex.status = cancelled ? 'cancelled' : 'exited';
    this.releaseExecLocks(t, ex.execId);
    this.event('exec_ended', { execId: ex.execId, taskId: t.taskId, code: res.code, signal: res.signal, cancelled, afterRestart: ex.observedAfterRestart });
    if (ex.observedAfterRestart) {
      // 서버 재시작 전후로 이어진 실행: 결과를 자동 반영하지 않고 사용자 확인을 기다린다.
      this.setStatus(t, 'exit_observed', `재시작 후 종료 관찰(code ${res.code}). '결과 반영'으로 await-exit 단계를 재개`);
      return;
    }
    // 최종 상태(검토 대기/실패/중단)는 workflow collect 단계가 정한다.
    this.setStatus(t, 'collecting', `종료 확인(code ${res.code}${cancelled ? ', 중단' : ''}) · 결과 수집 중`);
    await this.resume(t, ex, { execId: ex.execId, exitCode: res.code, signal: res.signal, cancelled });
  }

  private async resume(t: Task, ex: Execution, data: Record<string, unknown>) {
    if (!this.resumer || !ex.runId) return;
    try { await this.resumer(ex.runId, 'await-exit', data); }
    catch (err) { this.event('resume_error', { taskId: t.taskId, error: (err as Error).message }); t.statusReason = `workflow 재개 실패: ${(err as Error).message}`; this.save(); }
  }

  /** 서버 재시작 후 상태 복구. 살아 있는 프로세스·결과 불명 작업을 완료로 표시하거나 재실행하지 않는다. */
  private recover() {
    for (const ex of Object.values(this.state.executions)) {
      if (ex.status !== 'running' && ex.status !== 'cancelling') continue;
      if (ex.serverLifetime === this.lifetime) continue;
      ex.observedAfterRestart = true;
      const t = this.state.tasks[ex.taskId];
      if (fs.existsSync(ex.exitPath)) { /* tick에서 exit_observed로 정리 */ }
      else if (this.alive(ex.pid) && this.ownsLeader(ex)) this.setStatus(t, 'orphan_running', '서버 재시작 전 시작된 프로세스가 아직 실행 중(관찰만 함)');
      else if (this.groupAlive(ex.pgid)) this.setStatus(t, 'orphan_running', '감독자는 없고 같은 그룹 자식 프로세스만 남음');
      else { ex.status = 'unknown'; this.setStatus(t, 'unknown', '재시작 후 프로세스·종료 기록 모두 없음(결과 불명)'); }
    }
    for (const t of Object.values(this.state.tasks)) {
      if (t.status === 'starting') this.setStatus(t, 'unknown', '시작 도중 서버 종료(결과 불명)');
      if (t.status === 'integrating') this.setStatus(t, 'unknown', '통합 도중 서버 종료(통합 checkout을 직접 확인)');
    }
    this.save();
    this.ensureWatcher();
  }

  // ---------- 중단 ----------
  async cancel(taskId: string): Promise<{ ok: boolean; reason: string }> {
    const t = this.task(taskId);
    const ex = t.lastExecId ? this.state.executions[t.lastExecId] : null;
    if (!ex || !['running', 'cancelling'].includes(ex.status)) return { ok: false, reason: '이 실행기가 시작한 실행 중 프로세스가 없음' };
    const leader = this.ownsLeader(ex);
    if (leader === false) return { ok: false, reason: `PID ${ex.pid}가 이 실행기의 감독 프로세스가 아님(중단 거부)` };
    if (leader === null && !this.groupAlive(ex.pgid)) return { ok: false, reason: '프로세스 그룹이 이미 없음' };
    ex.cancelRequested = true; ex.status = 'cancelling';
    this.setStatus(t, 'cancelling', `SIGTERM → 프로세스 그룹 ${ex.pgid}`);
    try { process.kill(-ex.pgid, 'SIGTERM'); } catch { /* gone */ }
    setTimeout(() => { if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } }, 3000).unref?.();
    return { ok: true, reason: `프로세스 그룹 ${ex.pgid}에 SIGTERM (3초 후 남으면 SIGKILL)` };
  }

  cancelAll(reason: string) {
    for (const t of Object.values(this.state.tasks)) {
      if (['running', 'cancelling', 'orphan_running'].includes(t.status)) void this.cancel(t.taskId).then((r) => this.event("cancel_all", { taskId: t.taskId, trigger: reason, result: r.reason, ok: r.ok }));
    }
  }

  /** 결과 불명 확정: 프로세스 그룹이 없음을 확인한 뒤에만 잠금을 해제한다. */
  acknowledgeUnknown(taskId: string) {
    const t = this.task(taskId);
    if (t.status !== 'unknown') throw new UserError('결과 불명 상태가 아님');
    const ex = t.lastExecId ? this.state.executions[t.lastExecId] : null;
    if (ex && this.groupAlive(ex.pgid)) throw new UserError(`프로세스 그룹 ${ex.pgid}가 아직 살아 있음`);
    if (ex) { ex.status = 'abandoned'; this.releaseExecLocks(t, ex.execId); }
    this.setStatus(t, 'abandoned', '사용자가 결과 불명을 확정(완료로 보지 않음)');
  }

  /** 재시작 후 종료가 관찰된 실행을 사용자가 확인해 workflow await-exit 단계를 재개한다. */
  async applyObservedExit(taskId: string) {
    const t = this.task(taskId);
    if (t.status !== 'exit_observed') throw new UserError('재시작 후 종료 관찰 상태가 아님');
    const ex = this.state.executions[t.lastExecId!];
    this.setStatus(t, 'collecting', '사용자 확인 후 결과 반영');
    if (!this.resumer) throw new UserError('workflow 연결 없음');
    await this.resumer(ex.runId, 'await-exit', { execId: ex.execId, exitCode: ex.exitCode ?? null, signal: ex.signal ?? null, cancelled: ex.status === 'cancelled' });
  }

  // ---------- 결과 수집 ----------
  async collect(taskId: string, execId: string | null) {
    const t = this.task(taskId);
    const ex = execId ? this.state.executions[execId] : null;
    const checks: Check[] = [];
    const add = (name: string, ok: boolean, detail: string) => checks.push({ name, ok, detail });
    if (ex) add('종료코드', ex.exitCode === 0, `code=${ex.exitCode} signal=${ex.signal ?? '-'}${ex.spawnError ? ` spawn=${ex.spawnError}` : ''}`);
    const branchHead = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    const head = await G.revParse(t.worktree, 'HEAD');
    add('브랜치 HEAD 일치', !!head && head === branchHead, `HEAD ${head?.slice(0, 12)} / ${t.branch} ${branchHead?.slice(0, 12)}`);
    const anc = !!head && (await G.isAncestor(t.worktree, t.baseSha, head));
    add('기준 SHA 위의 커밋', anc, anc ? 'base..HEAD' : '기준 SHA의 후손이 아님');
    const commits = head && anc ? await G.commitsBetween(t.worktree, t.baseSha, head) : [];
    add('전달 커밋 존재', commits.length > 0, `${commits.length}개`);
    const changed = head && anc ? await G.changedFiles(t.worktree, t.baseSha, head) : [];
    const dirty = await G.dirtyFiles(t.worktree);
    add('미커밋 변경 없음', dirty.length === 0, dirty.length ? dirty.join(', ') : '깨끗함');
    const outOfScope = [...new Set([...changed, ...dirty])].filter((f) => !isAllowed(f, t.allowedFiles));
    add('허용 파일 범위', outOfScope.length === 0, outOfScope.length ? `범위 밖: ${outOfScope.join(', ')}` : `${changed.length}개 모두 허용 목록 안`);
    const checksPassed = checks.every((c) => c.ok);
    t.result = { execId, headSha: head, commits, changedFiles: changed, dirtyFiles: dirty, outOfScope, checks, checksPassed, collectedAt: new Date().toISOString() };
    const ok = !ex || (ex.exitCode === 0 && ex.status === 'exited');
    this.setStatus(t, ok ? 'review_pending' : ex?.status === 'cancelled' ? 'cancelled' : 'failed',
      ok ? (checksPassed ? '검토 대기' : '검토 대기(검사 실패 포함 — 승인 불가)') : ex?.status === 'cancelled' ? '사용자 중단' : `종료코드 ${ex?.exitCode ?? '없음'}${ex?.spawnError ? ` (${ex.spawnError})` : ''}`);
    return t.result;
  }

  async diff(taskId: string) {
    const t = this.task(taskId);
    const head = t.result?.headSha;
    if (!head) return '';
    return G.diffText(t.worktree, t.baseSha, head);
  }

  // ---------- 승인 ----------
  private async integrationState(t: Task, sha: string) {
    const files = (await G.changedFiles(t.worktree, t.baseSha, sha)).sort();
    const baseHead = await G.revParse(this.cfg.integration.checkout, `refs/heads/${this.cfg.integration.branch}`);
    return { files, filesHash: crypto.createHash('sha256').update(files.join('\0')).digest('hex'), baseHead };
  }

  async approve(taskId: string, sha: string): Promise<Approval> {
    const t = this.task(taskId);
    if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태가 아님(${t.status})`);
    if (!G.FULL_SHA.test(sha)) throw new UserError('전체 40자 SHA로 승인해야 함');
    if (!t.result?.checksPassed) throw new UserError('검사 실패가 있어 승인할 수 없음');
    const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    if (head !== sha || t.result.headSha !== sha) throw new UserError(`승인 SHA가 현재 결과와 다름(현재 ${head})`);
    if (!this.cfg.integration.checkout) throw new UserError('config.integration.checkout 미설정');
    const s = await this.integrationState(t, sha);
    if (!s.baseHead) throw new UserError('통합 기준 브랜치를 읽지 못함');
    t.approval = { sha, baseBranch: this.cfg.integration.branch, baseHead: s.baseHead, files: s.files, filesHash: s.filesHash, at: new Date().toISOString() };
    this.setStatus(t, 'approved', `SHA ${sha.slice(0, 12)} 승인 · 통합 실행 대기`);
    this.event('approved', { taskId, sha, baseHead: s.baseHead });
    return t.approval;
  }

  reject(taskId: string, reason: string) {
    const t = this.task(taskId);
    if (!['review_pending', 'approved', 'integration_refused', 'integration_blocked'].includes(t.status)) throw new UserError(`거절할 수 없는 상태(${t.status})`);
    t.approval = null;
    this.setStatus(t, 'rejected', reason || '사용자 거절');
  }

  // ---------- 통합 ----------
  async integrate(taskId: string): Promise<{ outcome: string; detail: string }> {
    const t = this.task(taskId);
    if (t.status !== 'approved' || !t.approval) throw new UserError(`승인된 상태가 아님(${t.status})`);
    if (this.tripped) throw new UserError('무료 가드 발동 상태');
    const owner = crypto.randomUUID();
    if (!this.locks.acquire('integration', { owner, taskId })) {
      return this.endIntegration(t, 'integration_blocked', `다른 통합 진행 중: ${JSON.stringify(this.locks.holder('integration'))}`, true);
    }
    try {
      this.setStatus(t, 'integrating');
      const a = t.approval;
      const checkout = this.cfg.integration.checkout;
      const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
      const s = await this.integrationState(t, a.sha);
      const branchNow = await G.currentBranch(checkout);
      const changes: string[] = [];
      if (head !== a.sha) changes.push(`작업 브랜치 SHA 변경 ${a.sha.slice(0, 12)} → ${head?.slice(0, 12)}`);
      if (branchNow !== a.baseBranch) changes.push(`통합 checkout 브랜치 ${branchNow} ≠ ${a.baseBranch}`);
      if (s.baseHead !== a.baseHead) changes.push(`기준 브랜치 이동 ${a.baseHead.slice(0, 12)} → ${s.baseHead?.slice(0, 12)}`);
      if (s.filesHash !== a.filesHash) changes.push('관련 파일 목록 변경');
      if (changes.length) {
        t.approval = null;
        return this.endIntegration(t, 'integration_refused', `승인 무효화: ${changes.join('; ')}`);
      }
      const dirty = (await G.dirtyFiles(checkout)).filter((f) => !f.startsWith('artifacts/'));
      const op = await G.operationInProgress(checkout);
      if (dirty.length || op) return this.endIntegration(t, 'integration_blocked', `통합 checkout이 깨끗하지 않음: ${op ?? dirty.join(', ')}`, true);
      const develop = path.join(checkout, 'develop');
      if (!fs.existsSync(develop)) return this.endIntegration(t, 'integration_blocked', '통합 checkout에 ./develop 없음', true);
      const commits = await G.commitsBetween(t.worktree, t.baseSha, a.sha);
      const r = await G.run(develop, ['--', 'git', 'cherry-pick', '-x', ...commits], checkout, 120_000, sanitizedChildEnv());
      if (r.code === 0) {
        const newHead = await G.revParse(checkout, 'HEAD');
        t.integration = { at: new Date().toISOString(), outcome: 'integrated', detail: r.stdout.slice(-2000), newHead, commits };
        return this.endIntegration(t, 'integrated', `통합 완료 → ${newHead}`);
      }
      if (/사용 중/.test(r.stderr)) return this.endIntegration(t, 'integration_blocked', `./develop 잠금 사용 중: ${r.stderr.trim()}`, true);
      const unmerged = (await G.git(checkout, 'diff', '--name-only', '--diff-filter=U')).stdout.split('\n').filter(Boolean);
      const abort = await G.run(develop, ['--', 'git', 'cherry-pick', '--abort'], checkout, 60_000, sanitizedChildEnv());
      t.integration = { at: new Date().toISOString(), outcome: 'conflict', detail: (r.stderr || r.stdout).slice(-2000), conflictFiles: unmerged, commits };
      t.approval = null;
      return this.endIntegration(t, 'integration_conflict', `충돌 파일: ${unmerged.join(', ') || '(확인 불가)'} · cherry-pick --abort ${abort.code === 0 ? '완료' : `실패(code ${abort.code}) — 통합 checkout 직접 확인 필요`}. 자동 ours/theirs·reset 없음.`);
    } finally {
      this.locks.release('integration', 'owner', owner);
    }
  }

  private endIntegration(t: Task, s: TaskStatus, detail: string, keepApproval = false) {
    if (!keepApproval && s !== 'integrated') t.approval = null;
    if (s !== 'integrated') t.integration = { ...(t.integration ?? {}), at: new Date().toISOString(), outcome: s, detail };
    this.setStatus(t, keepApproval && s === 'integration_blocked' ? 'approved' : s, detail);
    return { outcome: s, detail };
  }

  // ---------- 화면용 ----------
  logTail(execId: string, from = 0, max = 64_000) {
    const ex = this.state.executions[execId];
    if (!ex) throw new UserError('실행 없음');
    try {
      const size = fs.statSync(ex.logPath).size;
      const start = Math.max(from, size - max);
      const fd = fs.openSync(ex.logPath, 'r'); const buf = Buffer.alloc(size - start);
      fs.readSync(fd, buf, 0, buf.length, start); fs.closeSync(fd);
      return { text: buf.toString(), next: size };
    } catch { return { text: '', next: from }; }
  }

  async refreshProbes() {
    this.probes.codex = await probe('codex', this.cfg);
    this.probes.claude = await probe('claude', this.cfg);
    return this.probes;
  }

  groupsOf(t: Task) { return effectiveGroups(t); }
}

export class UserError extends Error {}
