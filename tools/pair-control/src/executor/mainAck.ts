// 인수 확인이 끝난 뒤: 메인을 바꾸고 세대를 올린 다음, 검증된 행동을 다음 감시 틱이 읽을 저장 상태로 남긴다.
import type { Executor } from './executor.ts';
import type { MainSession } from './mainTypes.ts';
import type { TakeoverResult } from './mainTakeover.ts';

export function ackSession(ex: Executor, s: MainSession, res: TakeoverResult) {
  const rt = ex.runtime, at = new Date().toISOString();
  ex.state.main = { agent: s.agent, since: at, reason: s.limitRecovery ? '한도 소진 복구' : '교대', history: [...(ex.state.main?.history ?? []), { agent: s.from, until: at }], memoFile: s.checkpointFile, generation: s.generation };
  rt.generation = s.generation; rt.frozen = false; s.status = 'taken_over'; s.ackedAt = at;
  s.pendingActions = res.actions ?? [];
  ex.audit('main_taken_over', { session: s.id, agent: s.agent, generation: s.generation });
  ex.store.save();
}
