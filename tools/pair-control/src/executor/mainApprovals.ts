// 승인 장부: 메인 역할이 바뀌어도 "기존에 승인된 범위"만 승계하고 범위 밖 행동은 막는다.
// 승인은 에이전트 이름이 아니라 근거·허용 행동·대상 저장소·브랜치·작업으로 기록한다. 이 도구는 승인을 만들어 내지 않고 기록·조회·검사만 한다.
import crypto from 'node:crypto';
import { UserError, type Executor } from './executor.ts';
import { HARD_DENIED, type Approval } from './mainTypes.ts';

const KNOWN_ACTIONS = ['assign_task', 'approve_task', 'integrate_task', 'run_experiment', ...HARD_DENIED];

/** 사용자가 이미 한 승인을 장부에 옮겨 적는다. 근거가 비어 있으면 승계 대상이 될 수 없으므로 거부한다. */
export function grantApproval(ex: Executor, input: { basis: string; actions: string[]; targets?: string[] | '*'; conditions?: string; boundSessionId?: string }): Approval {
  const basis = String(input.basis ?? '').trim();
  if (!basis) throw new UserError('승인 근거(원래 승인한 문서·발언)를 적어야 함');
  const actions = [...new Set((input.actions ?? []).map(String))];
  const bad = actions.filter((a) => !KNOWN_ACTIONS.includes(a));
  if (!actions.length || bad.length) throw new UserError(`허용 행동이 올바르지 않음: ${bad.join(', ') || '(없음)'}`);
  const a: Approval = {
    id: crypto.randomUUID(), basis: basis.slice(0, 400), actions, repo: ex.cfg.repo, branch: ex.cfg.integration.branch,
    targets: input.targets ?? '*', conditions: String(input.conditions ?? '').slice(0, 400), grantedAt: new Date().toISOString(),
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

/** 행동 하나가 승계된 승인 범위 안인지 검사한다. 안이면 근거 승인을, 밖이면 이유를 담은 UserError를 던진다. */
export function authorize(ex: Executor, sessionId: string | undefined, action: string, target: string): Approval {
  if ((HARD_DENIED as readonly string[]).includes(action)) throw new UserError(`${action}은(는) 어떤 승인으로도 자동 승계·수행하지 않음(사용자가 직접 지시해야 함)`);
  // 승계 가능한 승인(철회 안 됨, 세션 묶음은 현재 세션만)을 호출 깊이를 늘리지 않으려고 여기서 직접 거른다.
  const hit = ex.runtime.approvals.filter((a) => !a.revokedAt && (!a.boundSessionId || a.boundSessionId === sessionId)).find((a) => a.actions.includes(action) && a.repo === ex.cfg.repo && a.branch === ex.cfg.integration.branch && (a.targets === '*' || a.targets.includes(target)));
  if (hit) return hit;
  const bound = ex.runtime.approvals.some((a) => !a.revokedAt && a.boundSessionId && a.boundSessionId !== sessionId && a.actions.includes(action));
  throw new UserError(`승인 범위 밖: ${action} → ${target}${bound ? ' (다른 세션에 묶인 승인은 승계하지 않음)' : ''} — 기존 승인 절차를 따르세요`);
}
