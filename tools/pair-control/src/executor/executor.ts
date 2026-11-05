import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { Store, appendEvent } from './store.ts';
import { LockDir } from './locks.ts';
import { realReadiness, type Probe } from './adapters.ts';
import { scanArgs } from './nocharge.ts';
import { sanitizedChildEnv, type FreeGuard, type Alert } from './freeGuard.ts';
import { createExecutorGuard } from './executorGuard.ts';
import { recover } from './monitorRecovery.ts';
import { spawnSupervised } from './processSupervisor.ts';
import { limitFor } from './executorPolicy.ts';
import { UserError } from './errors.ts';
import type { PairConfig } from './config.ts';
import type { TaskInputT } from './contract.ts';
import type { EnvReadiness } from './envcheck.ts';
import type { Agent, MainOps, MainRuntime } from './mainTypes.ts';
export { UserError } from './errors.ts';

export type TaskStatus =
  | 'assigned' | 'blocked' | 'starting' | 'running' | 'collecting' | 'cancelling' | 'cancelled' | 'failed'
  | 'orphan_running' | 'exit_observed' | 'unknown' | 'abandoned'
  | 'manual_working' | 'review_pending' | 'approved' | 'rejected'
  | 'integrating' | 'integrated' | 'integrated_check_failed' | 'integration_refused' | 'integration_conflict' | 'integration_blocked';

/** 실행 잠금은 없어도 같은 파일의 결과가 아직 통합/거절되지 않은 상태. */
export const OCCUPYING: TaskStatus[] = ['starting', 'running', 'manual_working', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
  'review_pending', 'approved', 'integrating', 'integration_refused', 'integration_conflict', 'integration_blocked'];
export const STARTABLE: TaskStatus[] = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

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
  readonly state: State;
  readonly runtime: MainRuntime;
  readonly locks: LockDir;
  readonly guard: FreeGuard;
  readonly supervisorPath: string;
  readonly lifetime = crypto.randomUUID();
  readonly probes: Partial<Record<'codex' | 'claude', Probe>> = {};
  readonly logOffsets = new Map<string, number>();
  timer: NodeJS.Timeout | null = null;
  resumer: Resumer | null = null;
  guardAlert: Alert | null = null;
  mainOps: MainOps = {};
  ticking = false;
  stopped = false;

  constructor(readonly cfg: PairConfig, opts: { onTrip?: (a: Alert) => void } = {}) {
    fs.mkdirSync(cfg.stateDir, { recursive: true });
    this.store = new Store<State>(path.join(cfg.stateDir, 'state.json'), { tasks: {}, executions: {} });
    this.state = this.store.data;
    this.runtime = (this.state.mainRuntime ??= { generation: this.state.main?.generation ?? 0, frozen: false, session: null, history: [], approvals: [], processed: {}, limited: {}, failures: [] });
    this.locks = new LockDir(path.join(cfg.stateDir, 'locks'));
    this.supervisorPath = path.join(cfg.toolRoot, 'src', 'executor', 'supervisor.mjs');
    this.guard = createExecutorGuard(this, opts);
    this.guardAlert = this.guard.pending();
    recover(this);
  }

  get mainAgent(): 'codex' | 'claude' { return this.state.main?.agent ?? 'codex'; }

  audit(type: string, data: Record<string, unknown>) {
    appendEvent(this.cfg.stateDir, { type, lifetime: this.lifetime, ...data });
  }

  async launchMainProcess(o: { agent: Agent; bundleDir: string; prompt: string; sessionId: string }): Promise<string> {
    if (this.guardAlert) throw new UserError('과금 신호 감지 상태 — 새 메인을 실행하지 않음');
    const readiness = realReadiness(o.agent, this.probes[o.agent], this.cfg, { limit: limitFor(this, o.agent) });
    if (!readiness.available) throw new UserError(`실제 ${o.agent} 메인 실행 차단: ${readiness.blockers.map((blocker) => blocker.message).join(', ')}`);
    const args = o.agent === 'codex' ? ['exec', '--cd', o.bundleDir, '--sandbox', 'read-only', o.prompt] : ['--print', '--permission-mode', 'plan', o.prompt];
    const argRisks = scanArgs(args);
    if (argRisks.length) throw new UserError(`무과금 가드: ${argRisks.map((r) => r.message).join('; ')}`);
    const shown = args.map((a) => (a === o.bundleDir ? '<입력 묶음>' : a === o.prompt ? '<prompt>' : a));
    const ex = spawnSupervised(this, { taskId: '(main)', agent: o.agent, mode: 'real' }, { kind: 'main', runId: o.sessionId, cwd: o.bundleDir, command: this.probes[o.agent]!.binary!, args, env: sanitizedChildEnv(), display: [o.agent, ...shown] });
    return ex.execId;
  }
}
