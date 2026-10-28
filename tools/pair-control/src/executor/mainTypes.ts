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
  grantedAt: string;
  /** 특정 메인 세션에만 묶인 승인. 새 메인 세션은 이를 승계하지 않는다(이름만 바꿔 우회 금지). */
  boundSessionId?: string;
  revokedAt?: string;
}

export interface ActionResult { id: string; type: string; ok: boolean; detail: string; at: string }

export type SessionStatus = 'launching' | 'taken_over' | 'completed' | 'idle' | 'failed';

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
}

/** 메인 행동이 실제로 수행될 때 쓰는 연결부. 호출하는 쪽(서버·테스트)이 기존 기능을 그대로 넘긴다. */
export interface MainOps {
  assign?: (input: Record<string, unknown>) => Promise<unknown>;
  approve?: (taskId: string, sha: string) => Promise<unknown>;
  integrate?: (taskId: string) => Promise<unknown>;
}

/** 새 메인이 낼 수 있는 행동. 이 목록 밖 type은 지원하지 않는 행동으로 거부한다. */
export interface MainAction { id: string; type: string; taskId?: string; sha?: string; target?: string; input?: Record<string, unknown> }

export const HARD_DENIED = ['force_push', 'rewrite_history', 'expand_scope'] as const;
