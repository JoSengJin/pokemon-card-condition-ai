// 인수 확인과 분리된 세션 행동 적용 진입점. 저장된 taken_over 상태만 읽고, 적용 시작을 먼저 저장한다.
import { acceptActions, actionResults } from './actionState.ts';
import type { Executor } from './executor.ts';
import type { ActionResult, MainSession } from './mainTypes.ts';

export function finishSession(ex: Executor, s: MainSession) {
  const results = actionResults(s); s.actionResults.push(...results); delete s.actionWork; delete s.actionLifetime;
  let done = 0, did = false;
  for (const r of results) if (r.ok) { done++; if (r.type !== 'note') did = true; }
  s.status = did ? 'completed' : 'idle';
  if (did) s.completedAt = new Date().toISOString();
  ex.audit('main_handover_finished', { session: s.id, status: s.status, actions: results.length, done });
  ex.store.save();
}

export function applyTakenOver(ex: Executor, s: MainSession) {
  if (s.status === 'applying') {
    if (s.actionLifetime !== ex.lifetime) {
      s.status = 'idle'; s.failure = '서버 재시작 전 행동 적용 중이던 세션 — 결과 불명, 재시도하지 않음';
      ex.runtime.failures.push({ at: new Date().toISOString(), reason: s.failure, checkpointFile: s.checkpointFile });
      ex.store.save(); return;
    }
    return;
  }
  if (s.status !== 'taken_over') return;
  const actions = s.pendingActions ?? [];
  delete s.pendingActions; s.status = 'applying'; s.actionLifetime = ex.lifetime;
  acceptActions(ex, s, actions);
}
