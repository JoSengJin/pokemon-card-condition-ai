// 모델 없이 도구가 자동으로 시작하는 단계의 승인 범위. 행동 직전 검사(approvalGate.authorize)와 별개로, 무엇을 "시작"해도 되는지만 정한다.
//   ① 준비 권한: 지정 검사 실행·인계 문서 생성. prepare_checks 또는 confirm_handoff 승인이 열려 있을 때만(approve_task·integrate_task 승인으로 확대하지 않음).
//   ② 모델 턴 권한: 이벤트의 "다음 행동"에 필요한 승인이 모두 열려 있을 때만.
// 열린 승인 = 철회 안 됨 + 세션 묶음 일치 + 저장소·브랜치·대상 일치 + 자유 문장 조건 없음. 자유 문장 조건은 기계로 검증할 수 없으므로 사람 판단 전 자동 시작을 보류한다.
// 구조화 조건(requires)은 행동 직전에 기계 검사하므로 여기서는 풀지도 지우지도 않는다.
import { matches } from './approvalGate.ts';
import type { Executor, Task } from './executor.ts';
import type { EventKind } from './mainTypes.ts';

/** 준비 권한을 주는 승인 행동. approve_task·integrate_task 승인은 여기에 없다(준비 권한으로 확대하지 않음). */
export const PREP = ['prepare_checks', 'confirm_handoff'];

/**
 * 이 대상에서 actions 중 하나라도 덮는 "열린 승인"이 있으면 null, 없으면 보류 사유.
 * 열린 승인 = 철회 안 됨 + 세션 묶음 일치 + 저장소·브랜치·대상 일치 + 자유 문장 조건 없음.
 */
export function whyClosed(ex: Executor, sessionId: string | undefined, actions: string[], target: string): string | null {
  let withCondition = false;
  for (const a of ex.runtime.approvals) {
    if (a.revokedAt || (a.boundSessionId && a.boundSessionId !== sessionId)) continue;
    for (const action of actions) {
      if (!matches(ex, a, action, target)) continue;
      if (!a.conditions.trim()) return null;
      withCondition = true;
    }
  }
  const label = actions.join(' 또는 ');
  return withCondition ? `승인 조건 미확정: ${label} 승인에 검증할 수 없는 조건이 있어 사람 판단 전에는 자동 처리하지 않음` : `승인 범위 밖: ${label} 승인이 없어 자동 처리하지 않음`;
}

/** 이벤트가 모델 턴으로 이어질 때 처음 필요한 행동(작업, 승인 대상)들. 인계 확인 전이면 확인 승인, 확인 뒤면 승인(approve) 권한을 본다. */
function needs(ex: Executor, t: Task, kind: EventKind): [string, string][] {
  if (kind === 'result_ready') return [[t.handoff?.confirmedAt ? 'approve_task' : 'confirm_handoff', t.taskId]];
  if (kind === 'approved') return [['integrate_task', t.taskId]];
  return [['integrate_task', t.taskId], ['push_main', ex.cfg.integration.branch]];
}

/** 이 이벤트로 모델 턴을 시작해도 되는지. 되면 null, 아니면 보류 사유. */
export function turnHold(ex: Executor, sessionId: string | undefined, t: Task, kind: EventKind): string | null {
  for (const [action, target] of needs(ex, t, kind)) {
    const why = whyClosed(ex, sessionId, [action], target);
    if (why) return why;
  }
  return null;
}

/** 화면용: 승인이 열리지 않아 자동 준비를 시작하지 못한 결과 도착 작업과 사유. */
export function prepHolds(ex: Executor, sessionId: string | undefined): { key: string; reason: string }[] {
  const out: { key: string; reason: string }[] = [];
  for (const t of Object.values(ex.state.tasks)) {
    const head = t.result?.headSha, v = t.verification;
    if (t.status !== 'review_pending' || !head || (v?.sha === head && t.handoff)) continue;
    const why = whyClosed(ex, sessionId, PREP, t.taskId);
    if (why) out.push({ key: `prep:${t.taskId}:${head.slice(0, 8)}`, reason: `${t.taskId}: ${why}` });
  }
  return out;
}
