// 인수 확인이 끝난 뒤: 메인을 바꾸고 세대를 올리고 정지를 풀며, 새 메인이 낸 행동을 수행해 completed/idle로 마무리한다.
import { applyActions } from './mainActions.ts';
import type { Executor } from './executor.ts';
import type { ActionResult, MainSession } from './mainTypes.ts';
import type { TakeoverResult } from './mainTakeover.ts';

/** 수행한 행동 결과로 세션을 마무리한다. 상태 변경 행동이 하나라도 성공했을 때만 completed(교대 완료). */
function finishSession(ex: Executor, s: MainSession, results: ActionResult[]) {
  let done = 0, did = false;
  for (const r of results) if (r.ok) { done++; if (r.type !== 'note') did = true; }
  s.status = did ? 'completed' : 'idle';
  if (did) s.completedAt = new Date().toISOString();
  ex.audit('main_handover_finished', { session: s.id, status: s.status, actions: results.length, done });
  ex.store.save();
}

export async function ackSession(ex: Executor, s: MainSession, res: TakeoverResult) {
  const rt = ex.runtime, at = new Date().toISOString();
  ex.state.main = { agent: s.agent, since: at, reason: s.limitRecovery ? '한도 소진 복구' : '교대', history: [...(ex.state.main?.history ?? []), { agent: s.from, until: at }], memoFile: s.checkpointFile, generation: s.generation };
  rt.generation = s.generation; rt.frozen = false; s.status = 'taken_over'; s.ackedAt = at;
  ex.audit('main_taken_over', { session: s.id, agent: s.agent, generation: s.generation });
  ex.store.save();
  try { finishSession(ex, s, await applyActions(ex, s, res.actions ?? [])); } catch (e) {
    // 인수는 이미 검증을 통과했으므로 메인은 유지하되, 행동 수행 실패는 완료로 표시하지 않고 근거를 남긴다.
    s.status = 'idle'; s.failure = `행동 수행 중 예외: ${(e as Error).message}`;
    rt.failures.push({ at: new Date().toISOString(), reason: s.failure, checkpointFile: s.checkpointFile });
    ex.audit('main_handover_finished', { session: s.id, status: s.status, error: s.failure });
    ex.store.save();
  }
}
