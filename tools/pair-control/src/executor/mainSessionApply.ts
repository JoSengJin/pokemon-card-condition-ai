// 인수 확인과 분리된 세션 행동 적용 진입점. 저장된 taken_over 상태만 읽고, 적용 시작을 먼저 저장한다.
import { applyActions } from './mainActions.ts';
import type { Executor } from './executor.ts';
import type { ActionResult, MainSession } from './mainTypes.ts';

function finishSession(ex: Executor, s: MainSession, results: ActionResult[]) {
  let done = 0, did = false;
  for (const r of results) if (r.ok) { done++; if (r.type !== 'note') did = true; }
  s.status = did ? 'completed' : 'idle';
  if (did) s.completedAt = new Date().toISOString();
  ex.audit('main_handover_finished', { session: s.id, status: s.status, actions: results.length, done });
  ex.store.save();
}

export async function applyTakenOver(ex: Executor, s: MainSession) {
  if (s.status === 'applying') {
    s.status = 'idle'; s.failure = '서버 재시작 전 행동 적용 중이던 세션 — 결과 불명, 재시도하지 않음';
    ex.runtime.failures.push({ at: new Date().toISOString(), reason: s.failure, checkpointFile: s.checkpointFile });
    ex.store.save(); return;
  }
  if (s.status !== 'taken_over') return;
  const actions = s.pendingActions ?? [];
  delete s.pendingActions; s.status = 'applying'; ex.store.save();
  try { finishSession(ex, s, await applyActions(ex, s, actions)); } catch (e) {
    s.status = 'idle'; s.failure = `행동 수행 중 예외 — 일부 수행됐을 수 있어 재시도하지 않음: ${(e as Error).message}`;
    ex.runtime.failures.push({ at: new Date().toISOString(), reason: s.failure, checkpointFile: s.checkpointFile });
    ex.audit('main_handover_finished', { session: s.id, status: s.status, error: s.failure });
    ex.store.save();
  }
}
