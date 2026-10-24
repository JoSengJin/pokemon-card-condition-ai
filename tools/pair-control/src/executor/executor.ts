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
import { mockPlan, probe, realPlan, realReadiness, type LaunchPlan, type Probe } from './adapters.ts';
import { FreeGuard, sanitizedChildEnv, type Alert } from './freeGuard.ts';
import { commitContract, contractHashAt, contractPath } from './contractFile.ts';
import { checkVenv, neededEnv, type EnvReadiness } from './envcheck.ts';
import type { CheckSpecT } from './contract.ts';

export type TaskStatus =
  | 'assigned' | 'blocked' | 'starting' | 'running' | 'collecting' | 'cancelling' | 'cancelled' | 'failed'
  | 'orphan_running' | 'exit_observed' | 'unknown' | 'abandoned'
  | 'review_pending' | 'approved' | 'rejected'
  | 'integrating' | 'integrated' | 'integrated_check_failed' | 'integration_refused' | 'integration_conflict' | 'integration_blocked';

/** 실행 잠금은 없어도 같은 파일의 결과가 아직 통합/거절되지 않은 상태. */
export const OCCUPYING: TaskStatus[] = ['starting', 'running', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
  'review_pending', 'approved', 'integrating', 'integration_refused', 'integration_conflict', 'integration_blocked'];
const STARTABLE: TaskStatus[] = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export interface Check { name: string; ok: boolean; detail: string }

/** 작업 테스트·통합 후 검사 한 항목. 미실행(not_run)·중단·결과 불명은 통과가 아니다. */
export type CheckStatus = 'pending' | 'running' | 'passed' | 'failed' | 'cancelled' | 'unknown' | 'not_run';
export interface CheckRun {
  id: string; name: string; display: string[]; cwd: string; status: CheckStatus; sha: string;
  exitCode?: number | null; execId?: string; logPath?: string; startedAt?: string; endedAt?: string;
}
export interface Verification {
  runId: string; sha: string; contractHash: string; status: 'running' | 'passed' | 'failed' | 'cancelled' | 'unknown' | 'interrupted';
  items: CheckRun[]; startedAt: string; endedAt?: string; note?: string;
}

export type ReviewVerdict = 'approve' | 'changes_requested' | 'insufficient_evidence';
export const REVIEW_MOCK_SCENARIOS = ['approve', 'changes_requested', 'insufficient_evidence', 'slow-approve', 'wrong-sha', 'garbage', 'fail', 'hang'] as const;
export interface ReviewRecord {
  reviewId: string; reviewer: 'codex' | 'claude'; mode: 'mock' | 'real'; sha: string; contractHash: string; bundleDir: string;
  worktreeFingerprint: string;
  status: 'running' | 'done' | 'failed' | 'cancelled' | 'unknown'; verdict?: ReviewVerdict | null; summary?: string;
  execId?: string; startedAt: string; endedAt?: string; note?: string;
}

/** reviewVerdict는 감사 기록일 뿐 승인 조건이 아니다(리뷰 결과가 사람 승인을 대신하지 않음). */
export interface Approval { sha: string; baseBranch: string; baseHead: string; files: string[]; filesHash: string; contractHash: string; reviewVerdict: ReviewVerdict | null; at: string }

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
  /** 작업 브랜치에 커밋한 계약 파일의 커밋·내용 해시. Git 계약 검사·검사·승인의 기준. */
  contractPath: string;
  contractSha: string;
  contractHash: string;
  /** worktree 생성과 별개인 실행 준비 상태(자체 .venv·import 경로·필요 모듈). */
  envReadiness?: EnvReadiness;
  /** 에이전트 종료 후 실행기가 계약의 검사 명령을 별도로 실행한 결과(작업 테스트). */
  verification?: Verification | null;
  /** 별도 리뷰 작업(구현 worktree를 수정하지 않는 별도 CLI 실행). */
  review?: ReviewRecord | null;
  result?: {
    execId: string | null; headSha: string | null; commits: string[]; changedFiles: string[]; dirtyFiles: string[];
    outOfScope: string[]; checks: Check[]; checksPassed: boolean; collectedAt: string;
  } | null;
  approval?: Approval | null;
  integration?: {
    at: string; outcome: string; detail: string; newHead?: string | null; preHead?: string | null; conflictFiles?: string[]; commits?: string[];
    postStatus?: 'passed' | 'failed' | 'not_run'; postChecks?: CheckRun[];
  } | null;
}

export type ExecStatus = 'running' | 'cancelling' | 'exited' | 'cancelled' | 'unknown' | 'abandoned';
export type ExecKind = 'agent' | 'check' | 'review';
export interface Execution {
  /** agent=에이전트 CLI, check=작업 테스트(runId=검사 실행 ID), review=별도 리뷰 CLI(runId=리뷰 ID). 옛 기록은 agent. */
  kind?: ExecKind; checkId?: string; sha?: string;
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
    const t: Task = { ...input, worktree, status: 'assigned', createdAt: now, updatedAt: now, runHistory: [], usesDevelopLock: needsDevelopLock(input),
      contractPath: contractPath(input.taskId), contractSha: '', contractHash: '' };
    // 계약은 등록된 별도 worktree의 작업 브랜치에만 커밋한다(main·통합 checkout 금지).
    const must = ['설정', 'worktree 등록', '기본 checkout 분리', '브랜치', '기준 SHA', 'Git 진행 중 작업 없음'];
    const pre = (await this.preflightChecks(t)).filter((c) => must.includes(c.name) && !c.ok);
    if (pre.length) throw new UserError(`계약을 커밋할 수 없음: ${pre.map((c) => `${c.name}(${c.detail})`).join(', ')}`);
    try {
      const cc = await commitContract(worktree, input);
      t.contractSha = cc.contractSha; t.contractHash = cc.contractHash;
      this.event('contract_committed', { taskId: t.taskId, contractSha: cc.contractSha, reused: cc.reused });
    } catch (err) { throw new UserError((err as Error).message); }
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
    if (t.contractSha) {
      // 실행 준비: worktree가 있어도 자체 가상환경·import 경로가 준비되지 않으면 시작하지 않는다.
      t.envReadiness = await checkVenv(t.worktree, neededEnv(t, t.usesDevelopLock), t.requiredModules);
      for (const e of t.envReadiness.checks) add(`환경: ${e.name}`, e.ok, e.detail);
    }
    if (t.usesDevelopLock) {
      const dev = path.join(t.worktree, 'develop');
      let ok = false; try { fs.accessSync(dev, fs.constants.X_OK); ok = true; } catch { /* missing */ }
      add('./develop 잠금 경로', ok, ok ? '모델·worker 경로 → worktree의 ./develop -- <CLI> 로 실행' : 'worktree에 실행 가능한 ./develop 없음');
    }
    add('과금 신호', !this.tripped, this.tripped ? `감지됨: ${this.tripped.detail}` : '감지 없음(무료 보장 아님)');
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
    let command = plan.command, args = plan.args;
    if (t.mode === 'mock') args = [...args, '--counter', path.join(this.cfg.stateDir, 'mock-invocations.jsonl')];
    if (t.usesDevelopLock) { command = path.join(t.worktree, 'develop'); args = ['--', plan.command, ...args]; }
    const ex = this.spawnSupervised(t, { kind: 'agent', execId, runId, cwd: t.worktree, command, args,
      display: t.usesDevelopLock ? ['./develop', '--', ...plan.display] : plan.display });
    t.lastExecId = execId; t.runId = runId; t.runHistory = [...t.runHistory, runId];
    t.result = null; t.approval = null; t.integration = null; t.verification = null; t.review = null;
    this.setStatus(t, 'running');
    return { ok: true as const, execId, pid: ex.pid };
  }

  /** 감독 프로세스(새 프로세스 그룹)로 명령 하나를 실행한다. 에이전트·작업 테스트·리뷰가 같은 경로를 쓴다. */
  private spawnSupervised(t: Task, o: { kind: ExecKind; execId?: string; runId: string; cwd: string; command: string; args: string[]; display: string[]; checkId?: string; sha?: string }) {
    const execId = o.execId ?? crypto.randomUUID();
    const dir = path.join(this.cfg.stateDir, 'runs', execId);
    fs.mkdirSync(dir, { recursive: true });
    const token = crypto.randomUUID();
    const spec = { execId, token, cwd: o.cwd, command: o.command, args: o.args, env: sanitizedChildEnv(), logPath: path.join(dir, 'output.log'), exitPath: path.join(dir, 'exit.json') };
    const specPath = path.join(dir, 'spec.json');
    writeJsonAtomic(specPath, spec);
    fs.writeFileSync(spec.logPath, '');
    const sup = spawn(process.execPath, [this.supervisorPath, specPath], { cwd: o.cwd, detached: true, stdio: 'ignore', env: sanitizedChildEnv() });
    sup.unref();
    if (!sup.pid) throw new Error('감독 프로세스 시작 실패');
    const ex: Execution = {
      kind: o.kind, checkId: o.checkId, sha: o.sha,
      execId, taskId: t.taskId, runId: o.runId, token, agent: t.agent, mode: t.mode, display: o.display,
      pid: sup.pid, pgid: sup.pid, startedAt: new Date().toISOString(), status: 'running', cancelRequested: false,
      observedAfterRestart: false, serverLifetime: this.lifetime, logPath: spec.logPath, exitPath: spec.exitPath, specPath,
      tokens: '미측정', cost: '미측정',
    };
    this.state.executions[execId] = ex;
    this.event('exec_started', { taskId: t.taskId, kind: o.kind, execId, runId: o.runId, pid: ex.pid, display: ex.display });
    this.save();
    this.ensureWatcher();
    return ex;
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
        if ((ex.kind ?? 'agent') !== 'agent') {
          ex.status = ex.cancelRequested ? 'cancelled' : 'unknown'; ex.endedAt = new Date().toISOString();
          await this.onAuxEnd(ex, { code: null, cancelled: ex.cancelRequested, unknown: !ex.cancelRequested });
          continue;
        }
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
    if (res.token !== ex.token) {
      ex.status = 'unknown';
      if ((ex.kind ?? 'agent') !== 'agent') await this.onAuxEnd(ex, { code: null, cancelled: false, unknown: true });
      else this.setStatus(t, 'unknown', 'exit.json 토큰 불일치');
      return;
    }
    this.readNewLog(ex);
    if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } // 남은 손자 정리
    const cancelled = ex.cancelRequested || res.cancelRequested;
    ex.exitCode = res.code; ex.signal = res.signal; ex.spawnError = res.spawnError ?? null; ex.endedAt = res.endedAt;
    ex.status = cancelled ? 'cancelled' : 'exited';
    if ((ex.kind ?? 'agent') !== 'agent') { await this.onAuxEnd(ex, { code: res.code, cancelled, unknown: false }); return; }
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
      if ((ex.kind ?? 'agent') !== 'agent') {
        // 작업 테스트·리뷰: 살아 있으면 관찰만, 종료 기록이 있으면 tick에서 기록만 하고 다음 검사를 이어 실행하지 않는다.
        if (!fs.existsSync(ex.exitPath) && !this.groupAlive(ex.pgid)) { ex.status = 'unknown'; void this.onAuxEnd(ex, { code: null, cancelled: false, unknown: true }); }
        continue;
      }
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
    const ex = Object.values(this.state.executions).filter((e) => e.taskId === taskId && ['running', 'cancelling'].includes(e.status))
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
    if (!ex) return { ok: false, reason: '이 실행기가 시작한 실행 중 프로세스가 없음' };
    const leader = this.ownsLeader(ex);
    if (leader === false) return { ok: false, reason: `PID ${ex.pid}가 이 실행기의 감독 프로세스가 아님(중단 거부)` };
    if (leader === null && !this.groupAlive(ex.pgid)) return { ok: false, reason: '프로세스 그룹이 이미 없음' };
    ex.cancelRequested = true; ex.status = 'cancelling';
    if ((ex.kind ?? 'agent') === 'agent') this.setStatus(t, 'cancelling', `SIGTERM → 프로세스 그룹 ${ex.pgid}`);
    else { this.event('aux_cancel', { taskId, kind: ex.kind, execId: ex.execId }); this.save(); }
    try { process.kill(-ex.pgid, 'SIGTERM'); } catch { /* gone */ }
    setTimeout(() => { if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } }, 3000).unref?.();
    return { ok: true, reason: `${ex.kind ?? 'agent'} 프로세스 그룹 ${ex.pgid}에 SIGTERM (3초 후 남으면 SIGKILL)` };
  }

  cancelAll(reason: string) {
    const busy = new Set(Object.values(this.state.executions).filter((e) => ['running', 'cancelling'].includes(e.status)).map((e) => e.taskId));
    for (const t of Object.values(this.state.tasks)) {
      if (busy.has(t.taskId)) void this.cancel(t.taskId).then((r) => this.event("cancel_all", { taskId: t.taskId, trigger: reason, result: r.reason, ok: r.ok }));
    }
  }

  /** 사용자가 가상환경 등을 준비한 뒤 실행 준비 상태를 다시 확인한다(설치는 하지 않음). */
  async recheckEnv(taskId: string) {
    const t = this.task(taskId);
    t.preflight = await this.preflightChecks(t);
    this.save();
    return t.envReadiness;
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
    const anc = !!head && (await G.isAncestor(t.worktree, t.contractSha, head));
    add('계약 커밋 위의 작업', anc, anc ? `계약 ${t.contractSha.slice(0, 12)}..HEAD` : '계약 커밋의 후손이 아님');
    const hashNow = head ? await contractHashAt(t.worktree, t.taskId, head) : null;
    add('계약 파일 불변', hashNow === t.contractHash, hashNow === t.contractHash ? '등록 시 계약과 같음' : '계약 파일이 바뀌거나 사라짐(검사·승인 기준 무효)');
    const commits = head && anc ? await G.commitsBetween(t.worktree, t.contractSha, head) : [];
    add('전달 커밋 존재', commits.length > 0, `계약 이후 ${commits.length}개`);
    const changed = head && anc ? await G.changedFiles(t.worktree, t.contractSha, head) : [];
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
    if (!t.result?.checksPassed) throw new UserError('Git 계약 검사 실패가 있어 승인할 수 없음');
    const v = t.verification;
    if (!v || v.status !== 'passed') throw new UserError(`작업 테스트가 통과하지 않음(${v ? v.status : '미실행'}) — 미실행·실패·중단·결과 불명은 통과가 아님`);
    if (v.sha !== sha || v.contractHash !== t.contractHash) throw new UserError('작업 테스트 결과가 현재 SHA·계약과 다름 — 다시 실행');
    const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    if (head !== sha || t.result.headSha !== sha) throw new UserError(`승인 SHA가 현재 결과와 다름(현재 ${head})`);
    if (!this.cfg.integration.checkout) throw new UserError('config.integration.checkout 미설정');
    const s = await this.integrationState(t, sha);
    if (!s.baseHead) throw new UserError('통합 기준 브랜치를 읽지 못함');
    const rv = t.review && t.review.sha === sha && t.review.contractHash === t.contractHash && t.review.status === 'done' ? t.review.verdict ?? null : null;
    t.approval = { sha, baseBranch: this.cfg.integration.branch, baseHead: s.baseHead, files: s.files, filesHash: s.filesHash, contractHash: t.contractHash, reviewVerdict: rv, at: new Date().toISOString() };
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
      if (t.verification?.status !== 'passed' || t.verification.sha !== a.sha) changes.push('작업 테스트 결과가 승인 SHA와 다름');
      const hashAtSha = await contractHashAt(t.worktree, t.taskId, a.sha);
      if (hashAtSha !== a.contractHash || a.contractHash !== t.contractHash) changes.push('작업 계약 변경');
      if (changes.length) {
        t.approval = null;
        return this.endIntegration(t, 'integration_refused', `승인 무효화: ${changes.join('; ')}`);
      }
      const dirty = (await G.dirtyFiles(checkout)).filter((f) => !f.startsWith('artifacts/'));
      const op = await G.operationInProgress(checkout);
      if (dirty.length || op) return this.endIntegration(t, 'integration_blocked', `통합 checkout이 깨끗하지 않음: ${op ?? dirty.join(', ')}`, true);
      const develop = path.join(checkout, 'develop');
      if (!fs.existsSync(develop)) return this.endIntegration(t, 'integration_blocked', '통합 checkout에 ./develop 없음', true);
      // ./develop은 통합 checkout 자체의 .venv/bin/python으로 실행된다.
      const integEnv = await checkVenv(checkout, 'python');
      if (!integEnv.ready) return this.endIntegration(t, 'integration_blocked', `통합 checkout 실행 환경 미준비: ${integEnv.checks.filter((c) => !c.ok).map((c) => `${c.name}(${c.detail})`).join(', ')}`, true);
      const commits = await G.commitsBetween(t.worktree, t.baseSha, a.sha);
      const r = await G.run(develop, ['--', 'git', 'cherry-pick', '-x', ...commits], checkout, 120_000, sanitizedChildEnv());
      if (r.code === 0) {
        const newHead = await G.revParse(checkout, 'HEAD');
        const post = await this.runPostChecks(t, checkout, develop, { base: a.baseHead, head: newHead!, contract: t.contractSha });
        t.integration = { at: new Date().toISOString(), outcome: 'integrated', detail: r.stdout.slice(-2000), newHead, preHead: a.baseHead, commits, postStatus: post.status, postChecks: post.items };
        if (post.status === 'failed') {
          const bad = post.items.filter((i) => i.status !== 'passed').map((i) => `${i.name}(${i.status}, code ${i.exitCode ?? '-'})`).join(', ');
          return this.endIntegration(t, 'integrated_check_failed', `통합은 됐지만 통합 후 검사 실패: ${bad}. 통합 전 ${a.baseHead} / 통합 후 ${newHead}. 자동 되돌림 없음 — 확인 후 사람이 ./develop -- git revert 로 복구`);
        }
        return this.endIntegration(t, 'integrated', post.status === 'not_run' ? `통합 완료 → ${newHead} · 통합 후 검사 미지정(미실행)` : `통합 완료 → ${newHead} · 통합 후 검사 ${post.items.length}개 통과`);
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
    if (!keepApproval && s !== 'integrated' && s !== 'integrated_check_failed') t.approval = null;
    if (s !== 'integrated' && s !== 'integrated_check_failed') t.integration = { ...(t.integration ?? {}), at: new Date().toISOString(), outcome: s, detail };
    this.setStatus(t, keepApproval && s === 'integration_blocked' ? 'approved' : s, detail);
    return { outcome: s, detail };
  }

  // ---------- 작업 테스트(에이전트 종료 후 독립 실행) ----------
  /** 계약의 검사 명령을 구조화된 인자로 해석한다. 셸을 거치지 않고, cwd는 checkout 안으로 제한한다. */
  private resolveCheck(checkout: string, c: CheckSpecT, vars: { base: string; contract: string; head: string }) {
    const command = c.executable === 'node' ? process.execPath : c.executable === 'git' ? 'git' : path.join(checkout, '.venv', 'bin', 'python');
    const args = c.args.map((a) => a.replaceAll('{base}', vars.base).replaceAll('{contract}', vars.contract).replaceAll('{head}', vars.head));
    const cwd = path.resolve(checkout, c.cwd);
    if (cwd !== checkout && !cwd.startsWith(checkout + path.sep)) throw new UserError(`검사 cwd가 checkout 밖: ${c.cwd}`);
    return { command, args, cwd, display: [c.executable, ...args] };
  }

  /** 사용자가 확인한 뒤에만 호출된다(UI 확인 대화상자). 같은 작업의 중복 실행은 잠금으로 막는다. */
  async runChecks(taskId: string) {
    const t = this.task(taskId);
    if (this.tripped) throw new UserError('과금 신호 감지 상태 — 실행하지 않음');
    if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 작업 테스트를 실행(${t.status})`);
    if (!t.checks.length) throw new UserError('계약에 작업 테스트가 없음 — 승인할 수 없음(검사를 포함해 새 작업으로 준비)');
    if (t.verification?.status === 'running') throw new UserError('작업 테스트가 이미 실행 중');
    const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    if (!head || head !== t.result?.headSha) throw new UserError('Git 계약 검사 이후 코드 SHA가 바뀜 — 결과 재수집 필요');
    if ((await G.dirtyFiles(t.worktree)).length) throw new UserError('worktree에 미커밋 변경이 있음 — 커밋된 코드만 검사');
    const envr = await checkVenv(t.worktree, neededEnv(t, t.usesDevelopLock), t.requiredModules);
    t.envReadiness = envr;
    if (!envr.ready) throw new UserError(`실행 환경 미준비: ${envr.checks.filter((c) => !c.ok).map((c) => `${c.name}(${c.detail})`).join(', ')}`);
    const runId = crypto.randomUUID();
    const vars = { base: t.baseSha, contract: t.contractSha, head };
    const items: CheckRun[] = t.checks.map((c) => ({ id: c.id, name: c.name, display: this.resolveCheck(t.worktree, c, vars).display, cwd: c.cwd, status: 'pending', sha: head }));
    const names = [`task:${t.taskId}`, `worktree:${t.worktree}`];
    const got: string[] = [];
    for (const n of names) {
      if (!this.locks.acquire(n, { execId: runId, taskId, kind: 'check', lifetime: this.lifetime })) {
        for (const g of got) this.locks.release(g, 'execId', runId);
        throw new UserError(`잠금 사용 중: ${n}`);
      }
      got.push(n);
    }
    t.verification = { runId, sha: head, contractHash: t.contractHash, status: 'running', items, startedAt: new Date().toISOString() };
    this.event('checks_started', { taskId, runId, sha: head });
    this.save();
    await this.startNextCheck(t);
    return t.verification;
  }

  private async startNextCheck(t: Task): Promise<void> {
    const v = t.verification!;
    const item = v.items.find((i) => i.status === 'pending');
    if (!item) return this.finishVerification(t);
    const spec = t.checks.find((c) => c.id === item.id)!;
    const r = this.resolveCheck(t.worktree, spec, { base: t.baseSha, contract: t.contractSha, head: v.sha });
    try {
      const ex = this.spawnSupervised(t, { kind: 'check', runId: v.runId, cwd: r.cwd, command: r.command, args: r.args, display: r.display, checkId: item.id, sha: v.sha });
      item.status = 'running'; item.execId = ex.execId; item.logPath = ex.logPath; item.startedAt = ex.startedAt;
      this.save();
    } catch (err) {
      item.status = 'failed'; item.endedAt = new Date().toISOString(); v.note = `시작 실패: ${(err as Error).message}`;
      return this.startNextCheck(t);
    }
  }

  private finishVerification(t: Task, forced?: Verification["status"], note?: string): void {
    const v = t.verification!;
    for (const i of v.items) if (i.status === 'pending' || i.status === 'running') i.status = 'not_run';
    v.status = forced ?? (v.items.every((i) => i.status === 'passed') ? 'passed' : 'failed');
    if (note) v.note = note;
    v.endedAt = new Date().toISOString();
    for (const n of [`task:${t.taskId}`, `worktree:${t.worktree}`]) this.locks.release(n, 'execId', v.runId);
    this.event('checks_finished', { taskId: t.taskId, runId: v.runId, status: v.status, sha: v.sha });
    this.save();
  }

  /** 작업 테스트·리뷰 프로세스 종료 처리. 재시작 후 관찰된 종료는 기록만 하고 다음 단계를 자동으로 잇지 않는다. */
  private async onAuxEnd(ex: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
    const t = this.state.tasks[ex.taskId];
    if (ex.kind === 'review') return this.onReviewEnd(t, ex, r);
    const v = t.verification;
    if (!v || v.runId !== ex.runId) { this.save(); return; }
    const item = v.items.find((i) => i.execId === ex.execId);
    if (item) {
      item.status = r.unknown ? 'unknown' : r.cancelled ? 'cancelled' : r.code === 0 ? 'passed' : 'failed';
      item.exitCode = r.code; item.endedAt = new Date().toISOString();
    }
    if (r.unknown) return this.finishVerification(t, 'unknown', '검사 프로세스가 종료 기록 없이 사라짐(결과 불명) — 다시 실행 필요');
    if (r.cancelled) return this.finishVerification(t, 'cancelled', '사용자 중단');
    if (ex.observedAfterRestart) return this.finishVerification(t, 'interrupted', '서버 재시작으로 검사 순서가 끊김 — 남은 검사는 실행하지 않음. 다시 실행 필요');
    this.save();
    await this.startNextCheck(t);
  }

  /** 통합 checkout에서 ./develop 잠금 안으로 통합 후 검사를 실행한다. */
  private async runPostChecks(t: Task, checkout: string, develop: string, vars: { base: string; contract: string; head: string }) {
    const items: CheckRun[] = [];
    if (!t.postChecks.length) return { status: 'not_run' as const, items };
    for (const c of t.postChecks) {
      const r = this.resolveCheck(checkout, c, vars);
      const item: CheckRun = { id: c.id, name: c.name, display: ['./develop', '--', ...r.display], cwd: '.', status: 'running', sha: vars.head, startedAt: new Date().toISOString() };
      const res = await G.run(develop, ['--', r.command, ...r.args], checkout, 600_000, sanitizedChildEnv());
      const logPath = path.join(this.cfg.stateDir, 'runs', `post-${crypto.randomUUID()}.log`);
      fs.mkdirSync(path.dirname(logPath), { recursive: true });
      fs.writeFileSync(logPath, redact(res.stdout + (res.stderr ? `\n[stderr]\n${res.stderr}` : '')));
      item.status = res.code === 0 ? 'passed' : 'failed'; item.exitCode = res.code; item.logPath = logPath; item.endedAt = new Date().toISOString();
      items.push(item);
    }
    return { status: items.every((i) => i.status === 'passed') ? 'passed' as const : 'failed' as const, items };
  }

  // ---------- 리뷰(별도 CLI 작업) ----------
  /** 구현 worktree의 HEAD·미커밋 상태 지문. 리뷰 전후로 같아야 리뷰가 구현을 건드리지 않았다고 본다. */
  private async worktreeFingerprint(t: Task) {
    const head = await G.revParse(t.worktree, 'HEAD');
    const dirty = await G.dirtyFiles(t.worktree);
    return `${head}|${dirty.sort().join(',')}`;
  }

  /**
   * 고정 SHA·diff·계약·검사 결과를 묶어 별도 리뷰 작업으로 실행한다.
   * 리뷰 CLI는 묶음 폴더에서만 실행되고 구현 worktree 경로를 받지 않는다. 현재 대화창에 메시지를 보내는 것이 아니다.
   */
  async startReviewJob(taskId: string, o: { reviewer?: 'codex' | 'claude'; mode?: 'mock' | 'real'; mockScenario?: (typeof REVIEW_MOCK_SCENARIOS)[number] } = {}) {
    const t = this.task(taskId);
    if (this.tripped) throw new UserError('과금 신호 감지 상태 — 실행하지 않음');
    if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 리뷰를 등록(${t.status})`);
    const sha = t.result?.headSha;
    const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    if (!sha || head !== sha) throw new UserError('Git 계약 검사 이후 코드 SHA가 바뀜 — 결과 재수집 필요');
    const reviewer = o.reviewer ?? (t.agent === 'claude' ? 'codex' : 'claude');
    if (reviewer === t.agent) throw new UserError('구현 담당과 다른 에이전트가 리뷰해야 함');
    const mode = o.mode ?? 'mock';
    if (mode === 'mock' && o.mockScenario && !REVIEW_MOCK_SCENARIOS.includes(o.mockScenario)) throw new UserError(`알 수 없는 fake 리뷰 시나리오: ${o.mockScenario}`);
    if (t.review?.status === 'running') throw new UserError('리뷰가 이미 실행 중');
    const reviewId = crypto.randomUUID();
    if (!this.locks.acquire(`review:${taskId}`, { execId: reviewId, taskId, lifetime: this.lifetime })) throw new UserError('리뷰 잠금 사용 중');
    try {
      const bundleDir = path.join(this.cfg.stateDir, 'reviews', reviewId);
      fs.mkdirSync(bundleDir, { recursive: true });
      const contract = (await G.git(t.worktree, 'show', `${sha}:${t.contractPath}`)).stdout;
      fs.writeFileSync(path.join(bundleDir, 'contract.md'), contract);
      fs.writeFileSync(path.join(bundleDir, 'diff.patch'), await G.diffText(t.worktree, t.baseSha, sha, 2_000_000));
      writeJsonAtomic(path.join(bundleDir, 'checks.json'), {
        git_contract_checks: t.result!.checks,
        task_tests: t.verification && t.verification.sha === sha ? { status: t.verification.status, items: t.verification.items.map(({ logPath, ...i }) => ({ ...i, log: logPath && fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8').slice(-4000) : '' })) } : { status: 'not_run' },
      });
      writeJsonAtomic(path.join(bundleDir, 'meta.json'), { taskId, sha, baseSha: t.baseSha, contractSha: t.contractSha, contractHash: t.contractHash, implementer: t.agent, reviewer });
      fs.writeFileSync(path.join(bundleDir, 'REVIEW_REQUEST.md'), `# 리뷰 요청: ${taskId}

이 폴더만 읽는 별도 리뷰 작업이다. 구현 브랜치·worktree를 수정하지 않는다.
- contract.md: 작업 계약(목표·완료 조건·허용 파일·검사)
- diff.patch: 기준 ${t.baseSha} → 검토 대상 ${sha}
- checks.json: Git 계약 검사와 작업 테스트 결과(미실행은 통과가 아님)

판정을 아래 JSON 한 개로 review-result.json에 쓰거나 마지막 줄에 출력한다.
{"verdict": "approve | changes_requested | insufficient_evidence", "sha": "${sha}", "summary": "근거"}

판정은 사람 승인을 대신하지 않는다.
`);
      let command: string, args: string[], display: string[];
      if (mode === 'mock') {
        const script = path.join(this.cfg.toolRoot, 'mock', 'fake-reviewer.mjs');
        command = process.execPath; args = [script, '--scenario', o.mockScenario ?? 'approve', '--bundle', bundleDir];
        display = ['node', 'mock/fake-reviewer.mjs', '--scenario', o.mockScenario ?? 'approve', '--bundle', '<리뷰 묶음>'];
      } else {
        this.probes[reviewer] = await probe(reviewer, this.cfg);
        const rr = realReadiness(reviewer, this.probes[reviewer], this.cfg);
        if (!rr.available) throw new UserError(`실제 ${reviewer} 리뷰 차단: ${rr.blockers.map((b) => b.message).join(', ')}`);
        const prompt = 'REVIEW_REQUEST.md를 읽고 판정 JSON을 마지막 줄에 출력하세요. 파일을 수정하지 마세요.';
        // 옵션 이름은 --help로 확인하지만 값(read-only, plan)은 실제 CLI에서 별도 확인 필요.
        args = reviewer === 'codex' ? ['exec', '--cd', bundleDir, '--sandbox', 'read-only', prompt] : ['--print', '--permission-mode', 'plan', prompt];
        command = this.probes[reviewer]!.binary!; display = [reviewer, ...args.slice(0, -1).map((a) => (a === bundleDir ? '<리뷰 묶음>' : a)), '<prompt>'];
      }
      t.review = { reviewId, reviewer, mode, sha, contractHash: t.contractHash, bundleDir, worktreeFingerprint: await this.worktreeFingerprint(t), status: 'running', startedAt: new Date().toISOString() };
      const ex = this.spawnSupervised(t, { kind: 'review', runId: reviewId, cwd: bundleDir, command, args, display, sha });
      t.review.execId = ex.execId;
      this.event('review_started', { taskId, reviewId, reviewer, mode, sha });
      this.save();
      return t.review;
    } catch (err) {
      this.locks.release(`review:${taskId}`, 'execId', reviewId);
      if (t.review?.reviewId === reviewId) t.review = null;
      throw err instanceof UserError ? err : new UserError((err as Error).message);
    }
  }

  private async onReviewEnd(t: Task, ex: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
    const rv = t.review;
    this.locks.release(`review:${t.taskId}`, 'execId', ex.runId);
    if (!rv || rv.reviewId !== ex.runId) { this.save(); return; }
    rv.endedAt = new Date().toISOString();
    const done = (status: ReviewRecord['status'], note?: string, verdict: ReviewVerdict | null = null, summary?: string) => {
      rv.status = status; rv.note = note; rv.verdict = verdict; rv.summary = summary;
      this.event('review_finished', { taskId: t.taskId, reviewId: rv.reviewId, status, verdict });
      this.save();
    };
    if (r.unknown) return done('unknown', '리뷰 프로세스가 종료 기록 없이 사라짐(결과 불명)');
    if (r.cancelled) return done('cancelled', '사용자 중단');
    if ((await this.worktreeFingerprint(t)) !== rv.worktreeFingerprint) return done('failed', '리뷰 중 구현 worktree가 바뀜 — 결과를 쓰지 않음');
    if (r.code !== 0) return done('failed', `리뷰 CLI 종료코드 ${r.code}`);
    let parsed: any = null;
    const file = path.join(rv.bundleDir, 'review-result.json');
    try { parsed = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {
      const lines = (fs.existsSync(ex.logPath) ? fs.readFileSync(ex.logPath, 'utf8') : '').trim().split('\n').reverse();
      for (const l of lines) { try { const j = JSON.parse(l); if (j && typeof j === 'object' && 'verdict' in j) { parsed = j; break; } } catch { /* next */ } }
    }
    const verdicts: ReviewVerdict[] = ['approve', 'changes_requested', 'insufficient_evidence'];
    if (!parsed || !verdicts.includes(parsed.verdict)) return done('failed', '판정 형식을 읽지 못함 — "통과" 같은 문구만으로는 판정으로 보지 않음');
    if (parsed.sha !== rv.sha) return done('failed', `다른 SHA(${String(parsed.sha).slice(0, 12)})에 대한 판정 — 사용하지 않음`);
    return done('done', ex.observedAfterRestart ? '서버 재시작 후 종료 관찰' : undefined, parsed.verdict, String(parsed.summary ?? '').slice(0, 2000));
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

const SECRET_PATTERNS = [/sk-ant-[A-Za-z0-9_-]{8,}/g, /sk-[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{20,}/g, /Bearer\s+[A-Za-z0-9._-]{16,}/g];
function redact(s: string) { return SECRET_PATTERNS.reduce((acc, re) => acc.replace(re, '[REDACTED]'), s); }
