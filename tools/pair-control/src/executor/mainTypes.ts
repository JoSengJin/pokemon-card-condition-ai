// 메인 역할 교대 실행의 자료형. 함수는 없다(자료 구조만).
// 메인 역할은 에이전트 이름(codex/claude)과 분리된 "세대(generation)"를 가진 세션으로 다룬다.

export type Agent = 'codex' | 'claude';

/** 승인 장부 한 줄. 에이전트 이름이 아니라 근거·허용 행동·대상으로 기록하므로 메인이 바뀌어도 그대로 승계된다. */
export interface Approval {
  id: string;
  /** 원래 승인 근거(사용자 발언·문서 경로 등). 비어 있으면 승계하지 않는다. */
  basis: string;
  /** 허용 행동: assign_task | approve_task | integrate_task | run_experiment 등. force_push·rewrite_history·expand_scope는 기록해도 항상 거부한다. */
  actions: string[];
  repo: string;
  branch: string;
  /** 대상 작업 ID 목록 또는 '*'. run_experiment는 실험 ID를 여기에 적는다. */
  targets: string[] | '*';
  conditions: string;
  /** 기계로 검사하는 구조화 조건. 자유 문장(conditions)은 검사할 수 없으므로 있으면 자동 수행을 보류한다. */
  requires?: { handoffConfirmed?: boolean; selfReview?: boolean };
  grantedAt: string;
  /** 특정 메인 세션에만 묶인 승인. 새 메인 세션은 이를 승계하지 않는다(이름만 바꿔 우회 금지). */
  boundSessionId?: string;
  revokedAt?: string;
}

export interface ActionResult { id: string; type: string; ok: boolean; detail: string; at: string }
export type ActionStatus = 'accepted' | 'authorized' | 'dispatching' | 'done';
export interface ActionWork {
  action: MainAction; status: ActionStatus; target?: string; input?: Record<string, unknown>; selfReview?: boolean;
  dispatchLifetime?: string; pushStage?: 'plan' | 'scope' | 'lock' | 'exec'; pushPlanId?: string; pushTasks?: string[]; result?: ActionResult;
}

export type SessionStatus = 'launching' | 'taken_over' | 'applying' | 'completed' | 'idle' | 'failed';

export interface MainSession {
  id: string;
  agent: Agent;
  from: Agent;
  generation: number;
  status: SessionStatus;
  startedAt: string;
  limitRecovery: boolean;
  execId?: string;
  checkpointFile: string;
  checkpointHash: string;
  /** 세션 토큰의 해시(토큰 원문은 새 메인 프롬프트에만 있다). */
  tokenHash: string;
  ackedAt?: string;
  completedAt?: string;
  failure?: string;
  actionResults: ActionResult[];
  /** 인수 확인 뒤 저장된 행동. 다음 감시 틱이 적용을 시작하기 전에 지우고 applying을 저장한다. */
  pendingActions?: MainAction[];
  actionWork?: ActionWork[];
  actionLifetime?: string;
}

export interface MainRuntime {
  /** 현재 유효한 메인 세대. 인수 확인이 끝날 때만 올라간다. */
  generation: number;
  /** 교대 진행 중: 새 배정·승인·통합 같은 메인 상태 변경을 멈춘다. */
  frozen: boolean;
  session: MainSession | null;
  history: MainSession[];
  approvals: Approval[];
  /** 처리한 행동 ID(중복 명령 차단). */
  processed: Record<string, ActionResult>;
  /** 한도에 닿은 에이전트. 사용자가 풀렸음을 확인하기 전에는 그 에이전트로 교대하지 않는다. */
  limited: Partial<Record<Agent, { at: string; detail: string }>>;
  failures: { at: string; reason: string; checkpointFile?: string }[];
  lastCheckpoint?: string;
  /** 교대 뒤 연속 처리: 이벤트·턴·도구 단계 장부. 서버가 재시작되어도 이 장부로 중복 없이 이어간다. */
  pipeline?: PipelineState;
}

export type EventKind = 'result_ready' | 'approved' | 'integrated' | 'blocked';
export type EventState = 'pending' | 'launched' | 'applied' | 'held' | 'unknown';
/** 상태 변화 하나. key(종류+작업+SHA)가 같으면 한 번만 등록된다. blocked는 사람이 봐야 하는 멈춤이며 모델 턴을 일으키지 않는다. */
export interface PipelineEvent { key: string; kind: EventKind; taskId: string; sha: string; at: string; state: EventState; tried: number[]; turnId?: string; reason?: string }
export type TurnStatus = 'launching' | 'launched' | 'verified' | 'applying' | 'applied' | 'limited' | 'stale' | 'failed' | 'unknown';
/** 현재 메인에게 준 모델 턴 한 번. 같은 세션·세대의 승인 범위 안에서만 행동을 낸다. */
export interface MainTurn {
  id: string; sessionId: string; generation: number; agent: Agent; status: TurnStatus; eventKeys: string[]; startedAt: string; lifetime: string;
  execId?: string; tokenHash: string; checkpointFile: string; checkpointHash: string; actionResults: ActionResult[]; failure?: string;
  /** 검증을 통과해 저장된 응답의 행동(적용 전). 종료 관찰이 여기까지 기록하고, 적용은 연속 처리 진입점이 이 저장 상태를 읽어 따로 한다. */
  pendingActions?: MainAction[];
  actionWork?: ActionWork[];
  limitHandledAt?: string;
}
/** 새 턴을 막는 진행 중 상태. verified(검증 끝, 적용 전)도 포함한다. */
export const TURN_IN_FLIGHT: TurnStatus[] = ['launching', 'launched', 'verified', 'applying'];
export interface PipelineState {
  events: Record<string, PipelineEvent>; turns: Record<string, MainTurn>;
  /** 도구가 모델 없이 한 번만 수행하는 단계(검사·인계 생성)의 시도 기록. 같은 키는 다시 하지 않는다. */
  steps: Record<string, { at: string; ok: boolean; detail: string }>;
}

/** 메인 행동이 실제로 수행될 때 쓰는 연결부. 호출하는 쪽(서버·테스트)이 기존 기능을 그대로 넘긴다. */
export interface MainOps {
  assign?: (input: Record<string, unknown>) => Promise<unknown>;
  approve?: (taskId: string, sha: string) => Promise<unknown>;
  integrate?: (taskId: string) => Promise<unknown>;
}

/** 새 메인이 낼 수 있는 행동. 이 목록 밖 type은 지원하지 않는 행동으로 거부한다. */
export interface MainAction { id: string; type: string; taskId?: string; sha?: string; target?: string; input?: Record<string, unknown>; reviewedFiles?: string[]; diffHash?: string; note?: string }

export const HARD_DENIED = ['force_push', 'rewrite_history', 'expand_scope'] as const;

/** 새 메인 응답에서 허용하는 행동 종류(구조 검증용). 허용 여부는 승인 장부가 따로 판단한다. */
export const ACTION_TYPES = ['assign_task', 'approve_task', 'integrate_task', 'confirm_handoff', 'push_main', 'run_experiment', 'note', ...HARD_DENIED] as const;
