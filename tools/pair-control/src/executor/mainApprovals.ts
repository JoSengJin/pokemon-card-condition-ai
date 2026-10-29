// 승인 장부: 메인 역할이 바뀌어도 "기존에 승인된 범위"만 승계하고 범위 밖 행동은 막는다.
// 승인은 에이전트 이름이 아니라 근거·허용 행동·대상 저장소·브랜치·작업으로 기록한다. 이 도구는 승인을 만들어 내지 않고 기록·조회·검사만 한다.
// 행동 검사는 approvalGate.ts, 자동 준비·모델 턴의 시작 권한은 approvalScope.ts가 맡는다.
import crypto from 'node:crypto';
import { UserError, type Executor } from './executor.ts';
import { ACTION_TYPES, HARD_DENIED, type Approval } from './mainTypes.ts';

export { authorize } from './approvalGate.ts';

/**
 * prepare_checks는 모델이 제안하는 행동이 아니라 도구가 모델 없이 하는 준비 단계(지정 검사 실행·인계 문서 생성)의 권한이다.
 * 다른 행동 승인(특히 approve_task의 조건부 승인)으로 대신할 수 없고, 사용자가 따로 기록한다.
 */
const KNOWN_ACTIONS = ['assign_task', 'approve_task', 'integrate_task', 'confirm_handoff', 'push_main', 'run_experiment', 'prepare_checks', ...HARD_DENIED];
const REQUIRES = ['handoffConfirmed', 'selfReview'];

/** 구조화 조건과 행동 조합이 올바른지 확인한다. 어긋나면 UserError. */
function checkGrant(actions: string[], req: Record<string, unknown>) {
  const bad: string[] = [];
  for (const a of actions) if (!KNOWN_ACTIONS.includes(a)) bad.push(a);
  if (!actions.length || bad.length) throw new UserError(`허용 행동이 올바르지 않음: ${bad.join(', ') || '(없음)'}`);
  for (const [k, v] of Object.entries(req)) if (!REQUIRES.includes(k) || typeof v !== 'boolean') throw new UserError('지원하는 구조화 조건은 handoffConfirmed·selfReview(boolean)뿐');
  if (req.selfReview && (actions.length !== 1 || actions[0] !== 'confirm_handoff')) throw new UserError('selfReview 조건은 confirm_handoff 단독 승인에만 사용할 수 있음(구현 에이전트=메인의 자기 확인을 사용자가 명시적으로 허용할 때만)');
  if (req.handoffConfirmed && (actions.length !== 1 || actions[0] !== 'approve_task')) throw new UserError('handoffConfirmed 조건은 approve_task 단독 승인에만 사용할 수 있음');
}

/** 사용자가 이미 한 승인을 장부에 옮겨 적는다. 근거가 비어 있으면 승계 대상이 될 수 없으므로 거부한다. */
export function grantApproval(ex: Executor, input: { basis: string; actions: string[]; targets?: string[] | '*'; conditions?: string; requires?: { handoffConfirmed?: boolean; selfReview?: boolean }; boundSessionId?: string }): Approval {
  const basis = String(input.basis ?? '').trim();
  if (!basis) throw new UserError('승인 근거(원래 승인한 문서·발언)를 적어야 함');
  const actions = [...new Set((input.actions ?? []).map(String))], req = input.requires ?? {};
  checkGrant(actions, req);
  const a: Approval = {
    id: crypto.randomUUID(), basis: basis.slice(0, 400), actions, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    targets: input.targets ?? '*', conditions: String(input.conditions ?? '').slice(0, 400), grantedAt: new Date().toISOString(),
    ...(req.handoffConfirmed || req.selfReview ? { requires: { ...(req.handoffConfirmed ? { handoffConfirmed: true } : {}), ...(req.selfReview ? { selfReview: true } : {}) } } : {}),
    ...(input.boundSessionId ? { boundSessionId: input.boundSessionId } : {}),
  };
  ex.runtime.approvals.push(a);
  ex.audit('approval_recorded', { id: a.id, actions, targets: a.targets });
  ex.store.save();
  return a;
}

export function revokeApproval(ex: Executor, id: string): Approval {
  const a = ex.runtime.approvals.find((x) => x.id === id);
  if (!a) throw new UserError('승인 기록을 찾지 못함');
  a.revokedAt ??= new Date().toISOString();
  ex.audit('approval_revoked', { id });
  ex.store.save();
  return a;
}

/** 지금 새 메인이 승계할 수 있는 승인: 철회되지 않았고, 특정 세션에 묶인 것은 현재 세션 것만. */
export function inheritable(ex: Executor, sessionId: string | undefined): Approval[] {
  return ex.runtime.approvals.filter((a) => !a.revokedAt && (!a.boundSessionId || a.boundSessionId === sessionId));
}

/** 새 메인 요청문에 알려 줄 "모델이 제안할 수 있는 행동 종류". 도구의 준비 권한(prepare_checks)은 모델 행동이 아니므로 뺀다. */
export function modelActions(ex: Executor, sessionId: string | undefined): string[] {
  const out = new Set<string>();
  for (const a of inheritable(ex, sessionId)) for (const x of a.actions) if ((ACTION_TYPES as readonly string[]).includes(x)) out.add(x);
  return [...out];
}
