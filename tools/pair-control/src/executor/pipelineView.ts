// 화면용 연속 처리 요약. "메인 인수 완료"(세션), "개별 행동 성공"(턴 결과), "작업 파이프라인 완료"(원격 push 검증)를 따로 표시한다.
import { pipe } from './pipelineState.ts';
import type { Executor } from './executor.ts';

export function pipelineView(ex: Executor) {
  const p = pipe(ex), s = ex.runtime.session, pushes = Object.values(ex.state.pushes ?? {});
  const count = (st: string) => Object.values(p.events).filter((e) => e.state === st).length;
  return {
    takeoverDone: !!s?.ackedAt, session: s ? { id: s.id, status: s.status } : null,
    events: { pending: count('pending'), launched: count('launched'), applied: count('applied'), held: count('held'), unknown: count('unknown') },
    heldReasons: Object.values(p.events).filter((e) => e.state === 'held' || e.state === 'unknown').map((e) => ({ key: e.key, reason: e.reason ?? '' })),
    turns: Object.values(p.turns).slice(-5).map((t) => ({ id: t.id, agent: t.agent, generation: t.generation, status: t.status, actionsOk: t.actionResults.filter((r) => r.ok).length, actionsTotal: t.actionResults.length })),
    tasks: Object.values(ex.state.tasks).map((t) => ({ taskId: t.taskId, status: t.status, pipelineDone: pushes.some((x) => x.status === 'pushed_verified' && x.tasks.includes(t.taskId)) })),
  };
}
