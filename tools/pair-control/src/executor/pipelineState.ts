// 교대 뒤 연속 처리의 저장 장부 접근. 이벤트는 키(종류+작업+SHA)가 같으면 한 번만 등록되며, 상태 전이는 여기서만 한다.
import type { Executor } from './executor.ts';
import type { EventKind, EventState, PipelineEvent, PipelineState } from './mainTypes.ts';

export const pipe = (ex: Executor): PipelineState => (ex.runtime.pipeline ??= { events: {}, turns: {}, steps: {} });

/** 이벤트를 등록한다. 이미 있으면 새로 만들지 않는다(중복 이벤트 무시). 새로 등록했으면 true. */
export function register(ex: Executor, kind: EventKind, taskId: string, sha: string, hold?: string): boolean {
  const key = `${kind}:${taskId}:${sha}`, ev = pipe(ex).events;
  if (ev[key]) return false;
  ev[key] = { key, kind, taskId, sha, at: new Date().toISOString(), state: hold ? 'held' : 'pending', tried: [], ...(hold ? { reason: hold } : {}) };
  ex.audit('pipeline_event', { key, state: ev[key].state, reason: hold });
  return true;
}

/** 이벤트 묶음의 상태를 바꾼다(감사 기록 포함). */
export function mark(ex: Executor, keys: string[], state: EventState, extra: Partial<PipelineEvent> = {}) {
  const ev = pipe(ex).events;
  for (const k of keys) if (ev[k]) { Object.assign(ev[k], extra, { state }); ex.audit('pipeline_event_state', { key: k, state, reason: extra.reason }); }
  ex.store.save();
}
