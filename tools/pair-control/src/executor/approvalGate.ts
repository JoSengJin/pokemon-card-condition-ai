// 승인 장부의 행동 검사: 행동 하나가 승계된 승인 범위 안인지, 실행 맥락의 필수 조건까지 충족하는지 확인한다.
// 여러 승인이 같은 행동을 덮으면 기록 순서가 아니라 조건을 모두 충족하는 승인을 고른다(먼저 기록된 일반 승인이 명시적 예외 승인을 가리지 않음).
import { UserError, type Executor } from './executor.ts';
import { HARD_DENIED, type Agent, type Approval } from './mainTypes.ts';

/** 승인이 이 저장소·브랜치·행동·대상을 덮는지(상태·조건 검사 아님). */
export function matches(ex: Executor, a: Approval, action: string, target: string): boolean {
  return a.actions.includes(action) && a.repo === ex.cfg.repo && a.branch === ex.cfg.integration.branch && (a.targets === '*' || a.targets.includes(target));
}

/**
 * 승인의 조건을 기계로 확인한다. 통과하면 null, 아니면 이유.
 * 자유 문장 조건은 검사할 수 없으므로 항상 보류한다(조건 없는 승인으로 취급하지 않음).
 * 확인 행동에서 구현 에이전트가 메인과 같으면 독립 확인이 아니므로 selfReview를 명시한 승인만 충족한다.
 */
export function unmet(ex: Executor, a: Approval, action: string, target: string, mainAgent: Agent, sha?: string): string | null {
  if (a.conditions.trim()) return `검증할 수 없는 조건이 있어 자동 수행 보류(조건: ${a.conditions.trim().slice(0, 80)}) — 사람이 직접 처리하거나 구조화 조건으로 다시 기록하세요`;
  const t = ex.state.tasks[target], h = t?.handoff;
  if (action === 'confirm_handoff' && t && t.agent === mainAgent && !a.requires?.selfReview) return `${target}: 구현 에이전트(${t.agent})와 메인이 같아 독립 확인이 아님 — 사용자가 confirm_handoff 승인에 selfReview를 명시해야 함`;
  if (!a.requires?.handoffConfirmed) return null;
  const ok = !!h && !h.cancelledAt && !!h.confirmedAt && h.headSha === t.result?.headSha && (!sha || sha === h.headSha);
  return ok ? null : `조건 미충족: 현재 결과 SHA와 일치하는 메인 확인된 인계가 필요함(${target})`;
}

/** 행동 하나가 승계된 승인 범위 안인지 검사한다. 안이면 근거 승인을, 밖이면 이유를 담은 UserError를 던진다. */
export function authorize(ex: Executor, sessionId: string | undefined, action: string, target: string, sha?: string, context?: { generation: number; lifetime: string }): Approval {
  if (context && (ex.stopped || ex.runtime.frozen || ex.runtime.session?.id !== sessionId || ex.runtime.generation !== context.generation || ex.lifetime !== context.lifetime)) throw new UserError('이전 세대·수명 또는 교대/정지 중 요청 — 수행하지 않음');
  if ((HARD_DENIED as readonly string[]).includes(action)) throw new UserError(`${action}은(는) 어떤 승인으로도 자동 승계·수행하지 않음(사용자가 직접 지시해야 함)`);
  const reasons: string[] = [];
  let otherSession = false;
  for (const a of ex.runtime.approvals) {
    if (a.revokedAt || !a.actions.includes(action)) continue;
    if (a.boundSessionId && a.boundSessionId !== sessionId) { otherSession = true; continue; }
    if (!matches(ex, a, action, target)) continue;
    const why = unmet(ex, a, action, target, ex.mainAgent, sha);
    if (!why) return a;
    reasons.push(why);
  }
  if (reasons.length) throw new UserError(`승인 조건 불충족: ${action} → ${target} — ${reasons[0]}`);
  throw new UserError(`승인 범위 밖: ${action} → ${target}${otherSession ? ' (다른 세션에 묶인 승인은 승계하지 않음)' : ''} — 기존 승인 절차를 따르세요`);
}
