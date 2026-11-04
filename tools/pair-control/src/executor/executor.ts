import { onReviewEnd } from './reviewEnd.ts';
import { cancelManual } from './taskManual.ts';
import { setStatus, releaseExecLocks } from './taskState.ts';
import { spawnSupervised } from './processSupervisor.ts';
import { runPostChecks } from './verificationPost.ts';
import { worktreeFingerprint } from './reviewFingerprint.ts';
// Node 실행기: 작업 소유권·CLI 프로세스·Git 검사·취소·상태 저장·통합.
// Mastra workflow는 단계·승인 대기를 맡고, 실제 프로세스와 Git 상태의 근거는 이 실행기가 가진다.
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import type { PairConfig } from './config.ts';
import { appendEvent, Store, writeJsonAtomic } from './store.ts';
import { LockDir } from './locks.ts';
import * as G from './git.ts';
import { conflicts, isAllowed, needsDevelopLock, TaskInput, type ConflictReason, type TaskInputT } from './contract.ts';
import { chargeRisks, mockPlan, probe, realPlan, realReadiness, type LaunchPlan, type Probe } from './adapters.ts';
import { scanArgs } from './nocharge.ts';
import { scanOutput } from './streamGuard.ts';
import { FreeGuard, sanitizedChildEnv, type Alert } from './freeGuard.ts';
import { commitContract, contractHashAt, contractPath } from './contractFile.ts';
import { checkVenv, neededEnv, type EnvReadiness } from './envcheck.ts';
import { resolveCheck } from './checkCommand.ts';
import { buildStartPrompt } from './startPrompt.ts';
import type { Agent, MainOps, MainRuntime } from './mainTypes.ts';
import { onMainEnd } from './mainEnd.ts';
import { onTurnEnd } from './pipelineEnd.ts';
import { mark, pipe } from './pipelineState.ts';
import { pipelineTick } from './pipelineTick.ts';
import { advanceSessionLaunch } from './mainSessionLaunch.ts';
import { handoverAfterLimit } from './mainLimit.ts';
import { onLimitHit } from './limitScope.ts';
import { UserError } from './errors.ts';
export { UserError } from './errors.ts';

export type TaskStatus =
  | 'assigned' | 'blocked' | 'starting' | 'running' | 'collecting' | 'cancelling' | 'cancelled' | 'failed'
  | 'orphan_running' | 'exit_observed' | 'unknown' | 'abandoned'
  | 'manual_working' | 'review_pending' | 'approved' | 'rejected'
  | 'integrating' | 'integrated' | 'integrated_check_failed' | 'integration_refused' | 'integration_conflict' | 'integration_blocked';

/** 실행 잠금은 없어도 같은 파일의 결과가 아직 통합/거절되지 않은 상태. */
export const OCCUPYING: TaskStatus[] = ['starting', 'running', 'manual_working', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
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
  /** 메인 인계 자동 확인용 리뷰. 통과하면 인계를 자동 확인으로 기록한다(사람 승인은 아님). */
  forHandoff?: boolean;
}

/** reviewVerdict는 감사 기록일 뿐 승인 조건이 아니다(리뷰 결과가 사람 승인을 대신하지 않음). */
/**
 * 메인 에이전트에게 넘기는 인계 기록. 인계 문서는 작업 브랜치에 커밋하지 않는다(PAIR_CODING §4: 완료 후 추가 커밋 금지, SHA 고정).
 * 상태 폴더에 저장하고 복사용으로 보여 준다. 코드 SHA가 바뀌면 인계는 낡은 것으로 본다.
 */
export interface Handoff { at: string; to: 'codex' | 'claude'; headSha: string; file: string; confirmedAt?: string; note?: string; cancelledAt?: string; auto?: boolean;
  /** 자동 확인 리뷰가 approve가 아니거나 실패했을 때의 결과. 인계는 확인되지 않은 채 사람 차례로 남는다. */
  autoResult?: { at: string; status: string; verdict?: string | null; summary?: string } }

export interface Approval { sha: string; baseBranch: string; baseHead: string; files: string[]; filesHash: string; contractHash: string; reviewVerdict: ReviewVerdict | null; mainConfirmedAt: string | null; at: string }

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
  handoff?: Handoff | null;
  /** 보관 시각. 목록에서만 숨기며 기록·worktree·브랜치는 그대로 둔다(taskControl.ts). */
  archivedAt?: string | null;
  /** 폐기 기록(누가 왜 버렸는지 화면에 남김). 폐기해도 브랜치·worktree·기록은 지우지 않는다. */
  discard?: { at: string; reason: string } | null;
  /** 수동 모드: 사용자가 에이전트 세션에서 작업하는 동안의 소유권 기록. 프로세스는 없다. */
  manual?: { execId: string; runId: string; startedAt: string; endedAt?: string; ended?: 'finished' | 'cancelled' } | null;
  result?: {
    execId: string | null; headSha: string | null; commits: string[]; changedFiles: string[]; dirtyFiles: string[];
    outOfScope: string[]; checks: Check[]; checksPassed: boolean; collectedAt: string;
  } | null;
  approval?: Approval | null;
  integration?: {
    at: string; outcome: string; detail: string; newHead?: string | null; preHead?: string | null; conflictFiles?: string[]; commits?: string[];
    postStatus?: 'running' | 'passed' | 'failed' | 'not_run'; postChecks?: CheckRun[];
  } | null;
}

export type ExecStatus = 'running' | 'cancelling' | 'exited' | 'cancelled' | 'unknown' | 'abandoned';
export type ExecKind = 'agent' | 'check' | 'review' | 'main';
export interface Execution {
  /** agent=에이전트 CLI, check=작업 테스트(runId=검사 실행 ID), review=별도 리뷰 CLI(runId=리뷰 ID). 옛 기록은 agent. */
  kind?: ExecKind; checkId?: string; sha?: string;
  execId: string; taskId: string; runId: string; token: string; agent: string; mode: string; display: string[];
  pid: number; pgid: number; startedAt: string; endedAt?: string; status: ExecStatus;
  exitCode?: number | null; signal?: string | null; spawnError?: string | null; cancelRequested: boolean;
  observedAfterRestart: boolean; serverLifetime: string; logPath: string; exitPath: string; specPath: string;
  tokens: '미측정'; cost: '미측정';
  completion?: { stage: 'observed' | 'routing' | 'done'; code: number | null; cancelled: boolean; unknown: boolean; lifetime?: string };
}

/** 구독 사용 한도 도달 상태. 과금이 아니라 정지 신호이며, 사용자가 풀렸음을 확인하기 전에는 실제 실행을 시작하지 않는다. */
export interface LimitState { at: string; detail: string; source: string; agent?: string }
/** 메인 역할(통합·푸시·실험 단일 담당)의 현재 담당. 표시·기록용이며 권한을 강제하지 않는다. */
export interface MainRole { agent: 'codex' | 'claude'; since: string; reason?: string; history?: { agent: 'codex' | 'claude'; until: string }[]; memoFile?: string;
  /** 인수 확인이 끝난 메인 세션의 세대. 없으면 교대 기능 도입 전 기록이다. */
  generation?: number }
interface State {
  tasks: Record<string, Task>; executions: Record<string, Execution>; limit?: LimitState | null; main?: MainRole | null;
  /** 메인 교대 실행 상태(세대·세션·승인 장부·한도·처리한 행동). */
  mainRuntime?: MainRuntime | null;
  /** 푸시·되돌림 기록과 마지막 점검(push.ts). */
  pushes?: Record<string, import('./push.ts').PushRecord>; pushPlan?: import('./push.ts').PushPlan | null;
  /** 사용자가 오탐으로 확인한 비밀 패턴 항목(fingerprint = 커밋·파일·줄·패턴). */
  pushAllow?: Record<string, { at: string; file: string; line: number; commit: string }>;
}

export type Resumer = (runId: string, step: string, data: Record<string, unknown>) => Promise<void>;

export class Executor {
  readonly store: Store<State>;
  readonly locks: LockDir;
  readonly guard: FreeGuard;
  readonly lifetime = crypto.randomUUID();
  readonly probes: Partial<Record<'codex' | 'claude', Probe>> = {};
  private timer: NodeJS.Timeout | null = null;
  private logOffsets = new Map<string, number>();
  resumer: Resumer | null = null;
  private tripped: Alert | null = null;
  private ticking = false;

  constructor(readonly cfg: PairConfig, opts: { onTrip?: (a: Alert) => void } = {}) {
    fs.mkdirSync(cfg.stateDir, { recursive: true });
    this.store = new Store<State>(path.join(cfg.stateDir, 'state.json'), { tasks: {}, executions: {} });
    this.locks = new LockDir(path.join(cfg.stateDir, 'locks'));
    this.guard = new FreeGuard(cfg.stateDir, (a) => {
      this.tripped = a;
      this.audit('free_guard_trip', { ...a });
      this.cancelAll('무료 가드 발동');
      opts.onTrip?.(a);
    }, (a) => onLimitHit(this, a)); // 한도 출처의 공급자별 처리(limitScope.ts)
    this.tripped = this.guard.pending();
    this.recover();
  }

  get state() { return this.store.data; }
  setResumer(r: Resumer) { this.resumer = r; }
  get supervisorPath() { return path.join(this.cfg.toolRoot, 'src', 'executor', 'supervisor.mjs'); }
  get guardAlert() { return this.tripped; }
  /** 감사 기록(events.jsonl). push.ts 등 별도 모듈에서 쓴다. */
  audit(type: string, data: Record<string, unknown>) { appendEvent(this.cfg.stateDir, { type, lifetime: this.lifetime, ...data }); }
  get limit() { return this.state.limit ?? null; }
  /** 이 에이전트를 막는 한도: 전체 한도(구현 에이전트 한도) 또는 메인 세션이 낸 그 에이전트의 한도. */
  limitFor(agent: Agent): { at: string; detail: string } | null {
    return this.state.limit ?? this.runtime.limited[agent] ?? null;
  }
  /** 메인 교대 실행 상태. 처음 쓸 때 만든다. 세대는 인수 확인이 끝날 때만 올라간다. */
  get runtime(): MainRuntime {
    return (this.state.mainRuntime ??= { generation: this.state.main?.generation ?? 0, frozen: false, session: null, history: [], approvals: [], processed: {}, limited: {}, failures: [] });
  }
  mainOps: MainOps = {};
  setMainOps(ops: MainOps) { this.mainOps = ops; }
  /** 메인 교대 중에는 메인이 하는 상태 변경(배정·승인·통합 등)을 받지 않는다. */
  assertMainActive(op: string) {
    if (this.runtime.frozen) throw new UserError(`메인 교대 중 — ${op}을(를) 지금 할 수 없음(인수 확인 후 새 메인만 진행)`);
  }
  get mainAgent(): 'codex' | 'claude' { return this.state.main?.agent ?? 'codex'; }
  /** 사용자가 한도가 풀렸음을 확인했을 때만 호출한다. 재시도·크레딧 구매는 하지 않는다. */
  clearLimit() {
    if (!this.state.limit) throw new UserError('한도 도달 상태가 아님');
    this.audit('limit_cleared', { was: this.state.limit.at });
    this.state.limit = null;
    this.store.save();
    return null;
  }



  task(id: string) {
    const t = this.state.tasks[id];
    if (!t) throw new UserError(`task 없음: ${id}`);
    return t;
  }

  // ---------- 배정 ----------
  async assign(raw: unknown): Promise<Task> {
    this.assertMainActive('작업 배정');
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
      this.audit('contract_committed', { taskId: t.taskId, contractSha: cc.contractSha, reused: cc.reused });
    } catch (err) { throw new UserError((err as Error).message); }
    t.preflight = await this.preflightChecks(t);
    this.state.tasks[t.taskId] = t;
    this.audit('task_assigned', { taskId: t.taskId, agent: t.agent, mode: t.mode, branch: t.branch, baseSha: t.baseSha });
    this.store.save();
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
    if (t.mode === 'real') {
      // 실제 CLI는 구독 로그인으로만 시작한다. API 키·설정 주입·금지 옵션·한도 상태·사용자 확인 표시를 모두 본다.
      const risks = chargeRisks(t.agent, this.cfg, { worktree: t.worktree });
      for (const r of risks) add(`무과금: ${r.code}`, false, `${r.message} → ${r.fix}`);
      if (!risks.length) add('무과금 검사', true, '환경변수·설정에서 API 과금 경로 없음(로그인 방식은 확인 불가 — 사용자 확인 표시에 의존)');
      add('구독 확인 표시', this.cfg.confirmedSubscriptionAuth, this.cfg.confirmedSubscriptionAuth ? '사용자가 구독 로그인·추가 크레딧 꺼짐을 확인함' : 'config.confirmedSubscriptionAuth=false');
      const lim = this.limitFor(t.agent);
      add('구독 한도', !lim, lim ? lim.detail : '한도 도달 없음');
    }
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
    setStatus(this, t, 'starting');
    return { ok: true };
  }



  async launch(taskId: string, runId: string): Promise<{ ok: true; execId: string; pid: number } | { ok: true; manual: true; execId: null } | { ok: false; reason: string; conflicts?: ConflictReason[]; checks?: Check[] }> {
    const t = this.task(taskId);
    const execId = crypto.randomUUID();
    const r = this.reserve(t, execId);
    if (!r.ok) {
      const occupants = [...new Set((r.conflicts ?? []).map((c) => c.otherTask))].map((id) => `${id}[${this.state.tasks[id]?.status ?? '?'}]`).join(', ');
      const reason = r.conflicts?.length ? `${r.reason}: ${r.conflicts.map((c) => `${c.otherTask}(${c.kind} ${c.detail})`).join(', ')} — 점유 작업 ${occupants}. 필요 없으면 그 작업을 열어 "폐기"하세요` : r.reason;
      this.audit('start_refused', { taskId, reason });
      // 실행 중 작업의 중복 시작이면 상태를 건드리지 않고, 시작 가능한 작업이면 거절 사유만 남긴다.
      if (STARTABLE.includes(t.status)) { t.statusReason = `시작 거절: ${reason}`; t.updatedAt = new Date().toISOString(); this.store.save(); }
      return { ...r, reason };
    }
    try {
      const checks = await this.preflightChecks(t);
      t.preflight = checks;
      const failed = checks.filter((c) => !c.ok);
      if (t.mode === 'manual') {
        if (failed.length) {
          const reason = `사전 검사 실패: ${failed.map((c) => `${c.name}(${c.detail})`).join(', ')}`;
          releaseExecLocks(this, t, execId);
          setStatus(this, t, 'blocked', reason);
          return { ok: false, reason, checks };
        }
        // 수동 모드: 프로세스를 띄우지 않는다. 같은 잠금과 충돌 검사로 파일 소유권만 유지한다.
        t.manual = { execId, runId, startedAt: new Date().toISOString() };
        t.runId = runId; t.runHistory = [...t.runHistory, runId]; t.lastExecId = null;
        t.result = null; t.approval = null; t.integration = null; t.verification = null; t.review = null; t.handoff = null;
        t.permission = '수동 모드: 도구는 에이전트를 실행하지 않음. 에이전트 세션이 worktree에서 작업하며, 허용 파일은 "작업 완료" 후 diff로만 검사(실행 중 쓰기를 막지 않음).';
        setStatus(this, t, 'manual_working', '수동 작업 중 — 에이전트 세션에서 작업 후 "작업 완료"를 누르세요');
        this.audit('manual_started', { taskId, runId });
        return { ok: true as const, manual: true as const, execId: null };
      }
      let plan: LaunchPlan | { refused: string };
      if (t.mode === 'mock') plan = mockPlan(t, this.cfg);
      else {
        this.probes[t.agent] = await probe(t.agent, this.cfg);
        // 수동 경로와 같은 시작 프롬프트를 쓴다. 사용자가 자리에 없으므로 unattended(사람 정답 추정·재요청 금지)를 켠다.
        const start = await buildStartPrompt(t, this.mainAgent, { unattended: true });
        plan = realPlan(t, this.probes[t.agent]!, this.cfg, start.text);
      }
      if (failed.length || 'refused' in plan) {
        const reason = failed.length ? `사전 검사 실패: ${failed.map((c) => `${c.name}(${c.detail})`).join(', ')}` : (plan as { refused: string }).refused;
        releaseExecLocks(this, t, execId);
        setStatus(this, t, 'blocked', reason);
        return { ok: false, reason, checks };
      }
      t.permission = plan.permission;
      return this.spawnExec(t, runId, execId, plan);
    } catch (err) {
      releaseExecLocks(this, t, execId);
      setStatus(this, t, 'blocked', `시작 오류: ${(err as Error).message}`);
      return { ok: false, reason: (err as Error).message };
    }
  }

  private spawnExec(t: Task, runId: string, execId: string, plan: LaunchPlan) {
    let command = plan.command, args = plan.args;
    if (t.mode === 'mock') args = [...args, '--counter', path.join(this.cfg.stateDir, 'mock-invocations.jsonl')];
    if (t.usesDevelopLock) { command = path.join(t.worktree, 'develop'); args = ['--', plan.command, ...args]; }
    const ex = spawnSupervised(this, t, { kind: 'agent', execId, runId, cwd: t.worktree, command, args, env: sanitizedChildEnv(),
      display: t.usesDevelopLock ? ['./develop', '--', ...plan.display] : plan.display });
    t.lastExecId = execId; t.runId = runId; t.runHistory = [...t.runHistory, runId];
    t.result = null; t.approval = null; t.integration = null; t.verification = null; t.review = null; t.handoff = null;
    setStatus(this, t, 'running');
    return { ok: true as const, execId, pid: ex.pid };
  }

  /** 감독 프로세스(새 프로세스 그룹)로 명령 하나를 실행한다. 에이전트·작업 테스트·리뷰가 같은 경로를 쓴다. */


  /**
   * 새 메인 세션 프로세스를 실행한다. 리뷰와 같은 방식(읽기 전용·입력 묶음 폴더만 받음)이며 구독 로그인 가드와 한도 차단을 그대로 거친다.
   * 옵션 이름은 --help로 확인한 것만 쓰고, 세션 재개·도구 동작은 가정하지 않는다(별도 프로세스는 이전 대화 기억을 승계하지 않는다).
   */
  async launchMainProcess(o: { agent: Agent; bundleDir: string; prompt: string; sessionId: string }): Promise<string> {
    if (this.tripped) throw new UserError('과금 신호 감지 상태 — 새 메인을 실행하지 않음');
    const readiness = realReadiness(o.agent, this.probes[o.agent], this.cfg, { limit: this.limitFor(o.agent) });
    if (!readiness.available) throw new UserError(`실제 ${o.agent} 메인 실행 차단: ${readiness.blockers.map((blocker) => blocker.message).join(', ')}`);
    const args = o.agent === 'codex' ? ['exec', '--cd', o.bundleDir, '--sandbox', 'read-only', o.prompt] : ['--print', '--permission-mode', 'plan', o.prompt];
    const argRisks = scanArgs(args);
    if (argRisks.length) throw new UserError(`무과금 가드: ${argRisks.map((r) => r.message).join('; ')}`);
    const shown = args.map((a) => (a === o.bundleDir ? '<입력 묶음>' : a === o.prompt ? '<prompt>' : a));
    const ex = spawnSupervised(this, { taskId: '(main)', agent: o.agent, mode: 'real' }, { kind: 'main', runId: o.sessionId, cwd: o.bundleDir, command: this.probes[o.agent]!.binary!, args, env: sanitizedChildEnv(), display: [o.agent, ...shown] });
    return ex.execId;
  }

  // ---------- 감시 ----------
  ensureWatcher() {
    if (!this.timer) { this.timer = setInterval(() => void this.tick(), 300); this.timer.unref?.(); }
  }
  /** stop() 뒤에는 연속 처리가 새 검사·턴을 시작하지 않는다(정리 도중 비동기 시작 방지). */
  stopped = false;
  stop() { this.stopped = true; if (this.timer) clearInterval(this.timer); this.timer = null; }

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
      // 줄 단위 이벤트(JSON)가 읽는 중간에 잘렸으면 그 줄은 다음 주기에 이어 읽는다(조각이 일반 글로 검사되지 않게).
      let text = buf.toString(), used = buf.length;
      const cut = text.lastIndexOf('\n') + 1;
      if (text.slice(cut).startsWith('{') && size - off <= 1_000_000) { text = text.slice(0, cut); used = Buffer.byteLength(text); }
      this.logOffsets.set(ex.execId, off + used);
      return text;
    } catch { /* log not yet created */ }
    return '';
  }

  async tick() {
    if (this.ticking) return;
    this.ticking = true;
    try {
      const pending = Object.values(this.state.executions).find((row) => row.completion && row.completion.stage !== 'done');
      if (pending?.completion?.stage === 'observed') {
        pending.completion.stage = 'routing'; pending.completion.lifetime = this.lifetime; this.store.save(); return;
      }
      if (pending?.completion?.stage === 'routing') {
        const saved = pending.completion, stale = saved.lifetime !== this.lifetime;
        const result = stale ? { code: null, cancelled: false, unknown: true } : { code: saved.code, cancelled: saved.cancelled, unknown: saved.unknown };
        const turn = pending.kind === 'main' ? pipe(this).turns[pending.runId] : undefined;
        const task = this.state.tasks[pending.taskId];
        const check = pending.kind === 'check' ? task?.verification?.items.find((item) => item.execId === pending.execId) : undefined;
        const alreadyHandled = !!(stale && ((turn && turn.status !== 'launched') || (pending.kind === 'main' && !turn && this.runtime.session?.status !== 'launching') || (pending.kind === 'check' && check?.status !== 'running') || (pending.kind === 'review' && task?.review?.status !== 'running')));
        if (!alreadyHandled) {
          if (turn) await onTurnEnd(this, turn, pending, result);
          else if (pending.kind === 'main') await onMainEnd(this, pending, result);
          else if (pending.kind === 'review') await onReviewEnd(this, task, pending, result);
          else await this.onAuxEnd(pending, result);
        }
        saved.stage = 'done'; this.store.save(); return;
      }
    for (const ex of Object.values(this.state.executions)) {
      if (ex.status !== 'running' && ex.status !== 'cancelling') continue;
      const log = this.readNewLog(ex);
      if (log) scanOutput(this.guard, log, `exec:${ex.execId}`);
      if (fs.existsSync(ex.exitPath)) { await this.observeExit(ex); continue; }
      if (!this.alive(ex.pid)) {
        await new Promise((r) => setTimeout(r, 200));
        if (fs.existsSync(ex.exitPath)) { await this.observeExit(ex); continue; }
        if (this.groupAlive(ex.pgid)) continue; // 리더만 죽고 자식이 남은 경우: 정리 전까지 실행 중으로 본다
        const t = this.state.tasks[ex.taskId];
        if ((ex.kind ?? 'agent') !== 'agent') {
          ex.status = ex.cancelRequested ? 'cancelled' : 'unknown'; ex.endedAt = new Date().toISOString();
          ex.completion = { stage: 'observed', code: null, cancelled: ex.cancelRequested, unknown: !ex.cancelRequested };
          this.store.save();
          continue;
        }
        if (ex.cancelRequested) {
          ex.status = 'cancelled'; ex.endedAt = new Date().toISOString();
          releaseExecLocks(this, t, ex.execId);
          setStatus(this, t, 'collecting', '사용자 중단(강제 종료로 종료 기록 없음) · 결과 수집 중');
          await this.resume(t, ex, { execId: ex.execId, exitCode: null, signal: 'SIGKILL', cancelled: true });
        } else {
          ex.status = 'unknown';
          setStatus(this, t, 'unknown', '감독 프로세스가 종료 기록 없이 사라짐(결과 불명). 잠금 유지.');
        }
      }
    }
    for (const t of Object.values(this.state.tasks)) {
      const v = t.verification;
      if (v?.status !== 'running' || v.items.some((item) => item.status === 'running')) continue;
      await this.startNextCheck(t);
      return;
    }
    const launching = this.runtime.session;
    if (launching?.status === 'launching' && launching.launchStage) { await advanceSessionLaunch(this, launching); return; }
    const limited = Object.values(pipe(this).turns).find((turn) => turn.status === 'limited' && turn.limitHandledAt && !turn.limitHandoverDoneAt);
    if (limited) {
      if (!limited.limitHandoverStartedAt) { limited.limitHandoverStartedAt = new Date().toISOString(); limited.limitHandoverLifetime = this.lifetime; this.store.save(); return; }
      if (limited.limitHandoverLifetime !== this.lifetime) {
        limited.limitHandoverDoneAt = new Date().toISOString(); limited.failure = '서버 재시작 전 한도 교대 시작 — 결과 불명, 재시도하지 않음';
        mark(this, limited.eventKeys, 'unknown', { reason: limited.failure }); this.store.save(); return;
      }
      const other = limited.agent === 'codex' ? 'claude' : 'codex';
      await handoverAfterLimit(this, other, limited.eventKeys, `${limited.agent} 메인 한도 — 승인된 교대 절차 연결`);
      limited.limitHandoverDoneAt = new Date().toISOString(); this.store.save(); return;
    }
    await pipelineTick(this); // 교대 뒤 연속 처리: 상태를 읽고 새 이벤트가 있을 때만 현재 메인에게 턴을 준다
    } finally { this.ticking = false; }
  }

  private async observeExit(ex: Execution) {
    const t = this.state.tasks[ex.taskId];
    let res: any = {};
    try { res = JSON.parse(fs.readFileSync(ex.exitPath, 'utf8')); } catch { return; }
    if (res.token !== ex.token) {
      ex.status = 'unknown';
      if ((ex.kind ?? 'agent') !== 'agent') { ex.completion = { stage: 'observed', code: null, cancelled: false, unknown: true }; this.store.save(); }
      else setStatus(this, t, 'unknown', 'exit.json 토큰 불일치');
      return;
    }
    if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } // 남은 손자 정리
    const cancelled = ex.cancelRequested || res.cancelRequested;
    ex.exitCode = res.code; ex.signal = res.signal; ex.spawnError = res.spawnError ?? null; ex.endedAt = res.endedAt;
    ex.status = cancelled ? 'cancelled' : 'exited';
    if ((ex.kind ?? 'agent') !== 'agent') { ex.completion = { stage: 'observed', code: res.code, cancelled, unknown: false }; this.store.save(); return; }
    releaseExecLocks(this, t, ex.execId);
    this.audit('exec_ended', { execId: ex.execId, taskId: t.taskId, code: res.code, signal: res.signal, cancelled, afterRestart: ex.observedAfterRestart });
    if (ex.observedAfterRestart) {
      // 서버 재시작 전후로 이어진 실행: 결과를 자동 반영하지 않고 사용자 확인을 기다린다.
      setStatus(this, t, 'exit_observed', `재시작 후 종료 관찰(code ${res.code}). '결과 반영'으로 await-exit 단계를 재개`);
      return;
    }
    // 최종 상태(검토 대기/실패/중단)는 workflow collect 단계가 정한다.
    setStatus(this, t, 'collecting', `종료 확인(code ${res.code}${cancelled ? ', 중단' : ''}) · 결과 수집 중`);
    await this.resume(t, ex, { execId: ex.execId, exitCode: res.code, signal: res.signal, cancelled });
  }

  private async resume(t: Task, ex: Execution, data: Record<string, unknown>) {
    if (!this.resumer || !ex.runId) return;
    try { await this.resumer(ex.runId, 'await-exit', data); }
    catch (err) { this.audit('resume_error', { taskId: t.taskId, error: (err as Error).message }); t.statusReason = `workflow 재개 실패: ${(err as Error).message}`; this.store.save(); }
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
        if (!fs.existsSync(ex.exitPath) && !this.groupAlive(ex.pgid)) { ex.status = 'unknown'; ex.completion = { stage: 'observed', code: null, cancelled: false, unknown: true }; }
        continue;
      }
      if (fs.existsSync(ex.exitPath)) { /* tick에서 exit_observed로 정리 */ }
      else if (this.alive(ex.pid) && this.ownsLeader(ex)) setStatus(this, t, 'orphan_running', '서버 재시작 전 시작된 프로세스가 아직 실행 중(관찰만 함)');
      else if (this.groupAlive(ex.pgid)) setStatus(this, t, 'orphan_running', '감독자는 없고 같은 그룹 자식 프로세스만 남음');
      else { ex.status = 'unknown'; setStatus(this, t, 'unknown', '재시작 후 프로세스·종료 기록 모두 없음(결과 불명)'); }
    }
    for (const t of Object.values(this.state.tasks)) {
      if (t.status === 'starting') setStatus(this, t, 'unknown', '시작 도중 서버 종료(결과 불명)');
      if (t.status === 'integrating') setStatus(this, t, 'unknown', '통합 도중 서버 종료(통합 checkout을 직접 확인)');
    }
    this.store.save();
    this.ensureWatcher();
  }

  // ---------- 중단 ----------
  async cancel(taskId: string): Promise<{ ok: boolean; reason: string }> {
    const t = this.task(taskId);
    if (t.status === 'manual_working') return cancelManual(this, taskId);
    if (t.verification?.status === 'running' && !t.verification.items.some((item) => item.status === 'running')) {
      this.finishVerification(t, 'cancelled', '사용자 중단(검사 프로세스 시작 전)');
      return { ok: true, reason: '시작 전 작업 테스트 취소' };
    }
    return this.cancelRunning(taskId);
  }

  async cancelRunning(taskId: string): Promise<{ ok: boolean; reason: string }> {
    const t = this.task(taskId);
    const ex = Object.values(this.state.executions).filter((e) => e.taskId === taskId && ['running', 'cancelling'].includes(e.status))
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
    if (!ex) return { ok: false, reason: '이 실행기가 시작한 실행 중 프로세스가 없음' };
    const leader = this.ownsLeader(ex);
    if (leader === false) return { ok: false, reason: `PID ${ex.pid}가 이 실행기의 감독 프로세스가 아님(중단 거부)` };
    if (leader === null && !this.groupAlive(ex.pgid)) return { ok: false, reason: '프로세스 그룹이 이미 없음' };
    ex.cancelRequested = true; ex.status = 'cancelling';
    if ((ex.kind ?? 'agent') === 'agent') setStatus(this, t, 'cancelling', `SIGTERM → 프로세스 그룹 ${ex.pgid}`);
    else { this.audit('aux_cancel', { taskId, kind: ex.kind, execId: ex.execId }); this.store.save(); }
    try { process.kill(-ex.pgid, 'SIGTERM'); } catch { /* gone */ }
    setTimeout(() => { if (this.groupAlive(ex.pgid)) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } } }, 3000).unref?.();
    return { ok: true, reason: `${ex.kind ?? 'agent'} 프로세스 그룹 ${ex.pgid}에 SIGTERM (3초 후 남으면 SIGKILL)` };
  }

  /** 실행 중인 작업을 모두 중단한다. agent를 주면 그 공급자의 실행만 중단한다(다른 공급자의 진행 중 작업은 보존). */
  cancelAll(reason: string, agent?: string) {
    const busy = new Set(Object.values(this.state.executions).filter((e) => ['running', 'cancelling'].includes(e.status) && (!agent || e.agent === agent)).map((e) => e.taskId));
    for (const t of Object.values(this.state.tasks)) {
      if (busy.has(t.taskId)) void this.cancelRunning(t.taskId).then((r) => this.audit("cancel_all", { taskId: t.taskId, trigger: reason, result: r.reason, ok: r.ok }));
    }
  }

  // ---------- 메인 에이전트 인계 ----------
  /** 지금 누구 차례인지. 상태에서 파생하며 저장하지 않는다. 에이전트를 자동으로 부르지 못하므로 전환은 사용자가 한다. */




  /** 구현이 끝났음을 메인에게 넘긴다. 도구가 Git으로 교차 확인하며(커밋 없음·미커밋 변경·SHA 변경은 거절) 인계 문서는 상태 폴더에만 저장한다. */




  /** 메인 에이전트 세션에 붙여 넣을 한 줄 안내. */






  /** 잘못 누른 인계를 되돌린다. 코드·승인은 건드리지 않고 차례만 사용자에게 돌아온다. */


  // ---------- 에이전트에게 줄 시작 프롬프트 ----------


  // ---------- 수동 모드 ----------
  /** 사용자가 "작업 완료"를 눌렀다. 잠금을 풀고 workflow의 종료 대기 단계를 재개해 Git 계약 검사로 넘어간다. */




  /** 검토 단계에서 에이전트가 커밋을 더 했을 때 결과를 다시 수집한다. 이전 SHA의 작업 테스트·리뷰는 자동으로 무효(SHA 불일치)가 된다. */


  /** 사용자가 가상환경 등을 준비한 뒤 실행 준비 상태를 다시 확인한다(설치는 하지 않음). */


  /** 결과 불명 확정: 프로세스 그룹이 없음을 확인한 뒤에만 잠금을 해제한다. */


  /** 재시작 후 종료가 관찰된 실행을 사용자가 확인해 workflow await-exit 단계를 재개한다. */


  // ---------- 결과 수집 ----------




  // ---------- 승인 ----------


  /**
   * requireHandoff: 화면·API 승인은 앞 단계(리뷰가 돌고 있지 않음, 메인 인계 확인 완료)가 끝난 뒤에만 허용한다.
   * 내부 호출(테스트 등)은 기본 false로 기존 동작을 유지한다.
   */




  // ---------- 통합 ----------




  // ---------- 작업 테스트(에이전트 종료 후 독립 실행) ----------
  /** 계약의 검사 명령을 구조화된 인자로 해석한다. 셸을 거치지 않고, cwd는 checkout 안으로 제한한다. */

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
    const items: CheckRun[] = t.checks.map((c) => ({ id: c.id, name: c.name, display: resolveCheck(t.worktree, c, vars).display, cwd: c.cwd, status: 'pending', sha: head }));
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
    this.audit('checks_started', { taskId, runId, sha: head });
    this.store.save();
    this.ensureWatcher();
    return t.verification;
  }

  private async startNextCheck(t: Task): Promise<void> {
    const v = t.verification!;
    const item = v.items.find((i) => i.status === 'pending');
    if (!item) return this.finishVerification(t);
    const spec = t.checks.find((c) => c.id === item.id)!;
    const r = resolveCheck(t.worktree, spec, { base: t.baseSha, contract: t.contractSha, head: v.sha });
    try {
      const ex = spawnSupervised(this, t, { kind: 'check', runId: v.runId, cwd: r.cwd, command: r.command, args: r.args, env: sanitizedChildEnv(), display: r.display, checkId: item.id, sha: v.sha });
      item.status = 'running'; item.execId = ex.execId; item.logPath = ex.logPath; item.startedAt = ex.startedAt;
      this.store.save();
    } catch (err) {
      item.status = 'failed'; item.endedAt = new Date().toISOString(); v.note = `시작 실패: ${(err as Error).message}`;
      this.store.save();
    }
  }

  private finishVerification(t: Task, forced?: Verification["status"], note?: string): void {
    const v = t.verification!;
    for (const i of v.items) if (i.status === 'pending' || i.status === 'running') i.status = 'not_run';
    v.status = forced ?? (v.items.every((i) => i.status === 'passed') ? 'passed' : 'failed');
    if (note) v.note = note;
    v.endedAt = new Date().toISOString();
    for (const n of [`task:${t.taskId}`, `worktree:${t.worktree}`]) this.locks.release(n, 'execId', v.runId);
    this.audit('checks_finished', { taskId: t.taskId, runId: v.runId, status: v.status, sha: v.sha });
    this.store.save();
  }

  /** 작업 테스트·리뷰 프로세스 종료 처리. 재시작 후 관찰된 종료는 기록만 하고 다음 단계를 자동으로 잇지 않는다. */
  private async onAuxEnd(ex: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
    const t = this.state.tasks[ex.taskId];
    const v = t.verification;
    if (!v || v.runId !== ex.runId) { this.store.save(); return; }
    const item = v.items.find((i) => i.execId === ex.execId);
    if (item) {
      item.status = r.unknown ? 'unknown' : r.cancelled ? 'cancelled' : r.code === 0 ? 'passed' : 'failed';
      item.exitCode = r.code; item.endedAt = new Date().toISOString();
    }
    if (r.unknown) return this.finishVerification(t, 'unknown', '검사 프로세스가 종료 기록 없이 사라짐(결과 불명) — 다시 실행 필요');
    if (r.cancelled) return this.finishVerification(t, 'cancelled', '사용자 중단');
    if (ex.observedAfterRestart) return this.finishVerification(t, 'interrupted', '서버 재시작으로 검사 순서가 끊김 — 남은 검사는 실행하지 않음. 다시 실행 필요');
    this.store.save();
  }

  /** 통합 checkout에서 ./develop 잠금 안으로 통합 후 검사를 실행한다. */


  // ---------- 리뷰(별도 CLI 작업) ----------
  /** 구현 worktree의 HEAD·미커밋 상태 지문. 리뷰 전후로 같아야 리뷰가 구현을 건드리지 않았다고 본다. */


  /**
   * 고정 SHA·diff·계약·검사 결과를 묶어 별도 리뷰 작업으로 실행한다.
   * 리뷰 CLI는 묶음 폴더에서만 실행되고 구현 worktree 경로를 받지 않는다. 현재 대화창에 메시지를 보내는 것이 아니다.
   */




  /**
   * 인계용 리뷰가 끝났을 때 인계에 결과를 반영한다. approve이고 인계·SHA가 그대로일 때만 자동 확인으로 기록하고,
   * 그 밖(근거 부족·수정 필요·실패·중단·결과 불명)은 확인하지 않은 채 결과를 남겨 사람이 이유를 보고 결정하게 한다. 사람 승인은 대신하지 않는다.
   */


}
