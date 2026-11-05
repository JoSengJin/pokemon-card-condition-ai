import { ensureWatcher } from './monitorSchedule.ts';
import type { Executor } from './executor.ts';
import type { Agent } from './mainTypes.ts';

export interface GuardCancellation { at: string; reason: string; agent?: Agent; stage: 'pending' | 'dispatching' | 'sent' | 'unknown'; lifetime?: string }

/** 차단 상태와 취소 요청을 한 저장에 담는다. 실제 그룹 종료는 감시 진입점이 맡는다. */
export function queueGuardCancellation(ex: Executor, reason: string, agent?: Agent) {
  (ex.state.guardCancellations ??= []).push({ at: new Date().toISOString(), reason, agent, stage: 'pending' });
  ex.store.save();
  ensureWatcher(ex);
}
