// 승인 장부: 메인 역할이 바뀌어도 "기존에 승인된 범위"만 승계하고 범위 밖 행동은 막는다.
// 승인은 에이전트 이름이 아니라 근거·허용 행동·대상 저장소·브랜치·작업으로 기록한다. 이 도구는 승인을 만들어 내지 않고 기록·조회·검사만 한다.
import crypto from 'node:crypto';
import { UserError, type Executor } from './executor.ts';
import { HARD_DENIED, type Approval } from './mainTypes.ts';

const KNOWN_ACTIONS = ['assign_task', 'approve_task', 'integrate_task', 'confirm_handoff', 'push_main', 'run_experiment', ...HARD_DENIED];

/** 사용자가 이미 한 승인을 장부에 옮겨 적는다. 근거가 비어 있으면 승계 대상이 될 수 없으므로 거부한다. */
export function grantApproval(ex: Executor, input: { basis: string; actions: string[]; targets?: string[] | '*'; conditions?: string; requires?: { handoffConfirmed?: boolean; selfReview?: boolean }; boundSessionId?: string }): Approval {
  const basis = String(input.basis ?? '').trim();
  if (!basis) throw new UserError('승인 근거(원래 승인한 문서·발언)를 적어야 함');
  const actions = [...new Set((input.actions ?? []).map(String))];
  const bad = actions.filter((a) => !KNOWN_ACTIONS.includes(a));
  if (!actions.length || bad.length) throw new UserError(`허용 행동이 올바르지 않음: ${bad.join(', ') || '(없음)'}`);
  const req = input.requires ?? {};
  if (Object.keys(req).some((k) => !['handoffConfirmed', 'selfReview'].includes(k)) || Object.values(req).some((v) => typeof v !== 'boolean')) throw new UserError('지원하는 구조화 조건은 handoffConfirmed·selfReview(boolean)뿐');
  if (req.selfReview && (actions.length !== 1 || actions[0] !== 'confirm_handoff')) throw new UserError('selfReview 조건은 confirm_handoff 단독 승인에만 사용할 수 있음(구현 에이전트=메인의 자기 확인을 사용자가 명시적으로 허용할 때만)');
  if (req.handoffConfirmed && (actions.length !== 1 || actions[0] !== 'approve_task')) throw new UserError('handoffConfirmed 조건은 approve_task 단독 승인에만 사용할 수 있음');
  const a: Approval = {
    id: crypto.randomUUID(), basis: basis.slice(0, 400), actions, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    targets: input.targets ?? '*', conditions: String(input.conditions ?? '').slice(0, 400), grantedAt: new Date().toISOString(), ...(req.handoffConfirmed || req.selfReview ? { requires: { ...(req.handoffConfirmed ? { handoffConfirmed: true } : {}), ...(req.selfReview ? { selfReview: true } : {}) } } : {}),
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

/** 승인의 조건을 기계로 확인한다. 통과하면 null, 아니면 이유. 자유 문장 조건은 검사할 수 없으므로 항상 보류한다(조건 없는 승인으로 취급하지 않음). */
function unmet(ex: Executor, a: Approval, target: string, sha?: string): string | null {
  if (a.conditions.trim()) return `검증할 수 없는 조건이 있어 자동 수행 보류(조건: ${a.conditions.trim().slice(0, 80)}) — 사람이 직접 처리하거나 구조화 조건으로 다시 기록하세요`;
  if (!a.requires?.handoffConfirmed) return null;
  const t = ex.state.tasks[target], h = t?.handoff;
  const ok = !!h && !h.cancelledAt && !!h.confirmedAt && h.headSha === t.result?.headSha && (!sha || sha === h.headSha);
  return ok ? null : `조건 미충족: 현재 결과 SHA와 일치하는 메인 확인된 인계가 필요함(${target})`;
}

/** 행동 하나가 승계된 승인 범위 안인지 검사한다. 안이면 근거 승인을, 밖이면 이유를 담은 UserError를 던진다. 조건이 있는 승인은 조건까지 통과해야 한다. */
export function authorize(ex: Executor, sessionId: string | undefined, action: string, target: string, sha?: string): Approval {
  if ((HARD_DENIED as readonly string[]).includes(action)) throw new UserError(`${action}은(는) 어떤 승인으로도 자동 승계·수행하지 않음(사용자가 직접 지시해야 함)`);
  // 승계 가능한 승인(철회 안 됨, 세션 묶음은 현재 세션만)을 호출 깊이를 늘리지 않으려고 여기서 직접 거른다.
  const hits = ex.runtime.approvals.filter((a) => !a.revokedAt && (!a.boundSessionId || a.boundSessionId === sessionId)).filter((a) => a.actions.includes(action) && a.repo === ex.cfg.repo && a.branch === ex.cfg.integration.branch && (a.targets === '*' || a.targets.includes(target)));
  const reasons = hits.map((a) => unmet(ex, a, target, sha));
  const i = reasons.findIndex((r) => r === null);
  if (i >= 0) return hits[i];
  if (hits.length) throw new UserError(`승인 조건 불충족: ${action} → ${target} — ${reasons[0]}`);
  const bound = ex.runtime.approvals.some((a) => !a.revokedAt && a.boundSessionId && a.boundSessionId !== sessionId && a.actions.includes(action));
  throw new UserError(`승인 범위 밖: ${action} → ${target}${bound ? ' (다른 세션에 묶인 승인은 승계하지 않음)' : ''} — 기존 승인 절차를 따르세요`);
}

/** 이 작업을 덮는 승계 가능한 승인이 하나라도 있는지(도구가 모델 없이 하는 검사·인계 생성의 전제). 조건 충족까지는 보지 않는다. */
export function covers(ex: Executor, sessionId: string | undefined, taskId: string): boolean {
  const own = ['assign_task', 'approve_task', 'integrate_task', 'confirm_handoff'];
  return inheritable(ex, sessionId).some((a) => a.repo === ex.cfg.repo && a.branch === ex.cfg.integration.branch && a.actions.some((x) => own.includes(x)) && (a.targets === '*' || a.targets.includes(taskId)));
}
