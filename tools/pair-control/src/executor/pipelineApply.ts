// 검증이 끝나 저장된 턴(verified)의 행동을 적용한다. 종료 관찰(pipelineEnd.ts)과 다른 진입점이며 저장 상태만 읽는다.
// 적용을 시작하면 applying으로 먼저 저장해, 재시작 뒤에도 같은 응답을 다시 적용하지 않는다(결과 불명으로 보존).
// 적용 직전에 세션·세대·정지 상태를 다시 확인한다 — 검증 뒤 교대가 일어났으면 이전 세대의 응답은 아무것도 바꾸지 못한다.
import { acceptActions, actionResults } from './actionState.ts';
import { mark, pipe } from './pipelineState.ts';
import type { Executor } from './executor.ts';
import type { MainTurn } from './mainTypes.ts';

export function finishApplied(ex: Executor, t: MainTurn) {
  t.actionResults = actionResults(t); delete t.actionWork;
  let ok = 0;
  for (const r of t.actionResults) if (r.ok) ok++;
  t.status = 'applied';
  mark(ex, t.eventKeys, 'applied', { reason: `행동 ${ok}/${t.actionResults.length} 성공` });
  ex.audit('pipeline_turn_finished', { turn: t.id, ok, total: t.actionResults.length });
  ex.store.save();
}

/** 검증된 턴을 하나씩 적용한다(감시 틱의 연속 처리가 부른다). 정지되면 남은 턴은 적용하지 않고 저장 상태로 둔다. */
export function applyVerified(ex: Executor) {
  for (const t of Object.values(pipe(ex).turns)) {
    if (ex.stopped) return;
    if (t.status !== 'verified') continue;
    const rt = ex.runtime;
    if (rt.session?.id !== t.sessionId || rt.generation !== t.generation || rt.frozen) {
      delete t.pendingActions; t.status = 'stale';
      t.failure = '검증 뒤 세션·세대가 바뀜 — 이전 응답은 적용하지 않음(새 메인이 다시 판단)';
      mark(ex, t.eventKeys, 'pending', { reason: t.failure });
      return;
    }
    const actions = t.pendingActions ?? [];
    delete t.pendingActions; t.status = 'applying'; t.lifetime = ex.lifetime; acceptActions(ex, t, actions);
    return;
  }
}
