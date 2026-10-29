// 화면용 연속 처리 요약. "메인 인수 완료"(세션), "개별 행동 성공"(턴 결과), "작업 파이프라인 완료"(원격 push 검증)를 따로 표시한다.
// 보류·결과 불명 사유는 이벤트 장부와, 승인이 열리지 않아 자동 준비를 시작하지 못한 작업(prepHolds)에서 모은다.
import { prepHolds } from './approvalScope.ts';
import { pipe } from './pipelineState.ts';
import type { Executor } from './executor.ts';
import { TURN_IN_FLIGHT, type ActionResult, type EventState, type MainTurn } from './mainTypes.ts';

const actionRow = (r: ActionResult) => ({ id: r.id, type: r.type, ok: r.ok, detail: r.detail });

function turnRow(t: MainTurn) {
  let ok = 0;
  for (const r of t.actionResults) if (r.ok) ok++;
  return { id: t.id, agent: t.agent, generation: t.generation, status: t.status, inFlight: TURN_IN_FLIGHT.includes(t.status), startedAt: t.startedAt, failure: t.failure ?? null, events: t.eventKeys.length, actionsOk: ok, actionsTotal: t.actionResults.length, actions: t.actionResults.map(actionRow) };
}

/** 사람이 봐야 하는 사유: 보류·결과 불명 이벤트 + 승인이 열리지 않아 시작하지 못한 자동 준비. */
function heldRows(ex: Executor): { key: string; reason: string }[] {
  const out = prepHolds(ex, ex.runtime.session?.id);
  for (const e of Object.values(pipe(ex).events)) if (e.state === 'held' || e.state === 'unknown') out.push({ key: e.key, reason: `${e.state === 'unknown' ? '[결과 불명] ' : ''}${e.reason ?? ''}` });
  return out;
}

/** 원격 push가 검증된 작업 ID. 통합만으로는 파이프라인 완료가 아니다. */
function pushedTasks(ex: Executor): Set<string> {
  const done = new Set<string>();
  for (const p of Object.values(ex.state.pushes ?? {})) if (p.status === 'pushed_verified') for (const id of p.tasks) done.add(id);
  return done;
}

export function pipelineView(ex: Executor) {
  const p = pipe(ex), s = ex.runtime.session, pushed = pushedTasks(ex);
  const counts: Record<EventState, number> = { pending: 0, launched: 0, applied: 0, held: 0, unknown: 0 };
  for (const e of Object.values(p.events)) counts[e.state]++;
  const turns = Object.values(p.turns).slice(-5).map(turnRow); // 장부는 생성 순서대로 저장된다
  let current = turns[turns.length - 1] ?? null;
  for (const t of turns) if (t.inFlight) current = t; // 진행 중인 턴이 있으면 그 턴, 없으면 가장 최근 턴
  return {
    takeoverDone: !!s?.ackedAt, session: s ? { id: s.id, status: s.status } : null,
    takeover: s ? { agent: s.agent, from: s.from, generation: s.generation, status: s.status, acked: !!s.ackedAt, limitRecovery: s.limitRecovery } : null,
    events: counts, heldReasons: heldRows(ex), turns, currentTurn: current,
    tasks: Object.values(ex.state.tasks).map((t) => ({ taskId: t.taskId, status: t.status, pipelineDone: pushed.has(t.taskId) })),
  };
}
