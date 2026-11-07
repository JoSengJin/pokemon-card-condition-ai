import { limitFor } from './executorPolicy.ts';
// 감시 틱(기존 300ms 감시 루프)이 부르는 연속 처리 진입점. 상태를 읽을 뿐이며, 새 이벤트가 있을 때만 현재 메인에게 턴 한 번을 준다.
// 폴링으로 모델을 부르지 않는다: 같은 이벤트·같은 세대에는 턴이 한 번뿐이고, 진행 중 턴·교대 중·한도 중에는 아무것도 하지 않는다.
import { applyVerified, finishApplied } from './pipelineApply.ts';
import { authorizeAction } from './actionAuthorize.ts';
import { actionsDone, finishAction, type ActionOwner } from './actionState.ts';
import { mark, pipe } from './pipelineState.ts';
import { applyTakenOver, finishSession } from './mainSessionApply.ts';
import { TURN_IN_FLIGHT, type MainTurn } from './mainTypes.ts';
import type { Executor } from './executor.ts';

const RESTART_UNKNOWN = ['launching', 'launched', 'applying']; // 재시작 때 결과 불명으로 남기는 상태(verified는 검증된 저장 응답이라 최초 1회 적용 대상)
const busy = new WeakSet<object>(); // 겹쳐 호출돼도 한 번에 하나만(턴 이중 시작 방지)

/**
 * 재시작 복구 정책(두 경우를 구분한다):
 *  ① 결과 불명 보존 — 이전 서버 수명에서 끝맺지 못한 턴(launching·applying, 프로세스가 사라진 launched)은 결과 불명으로 남기고 다시 실행·적용하지 않는다.
 *  ② 검증 가능한 저장 응답의 최초 적용 — 재시작 사이에 프로세스가 끝나 종료 기록과 응답이 저장돼 있고 아직 적용 전(launched)인 턴은,
 *     감시 루프(recover)가 종료를 관찰해 onTurnEnd로 넘기며 같은 검증(세션·세대·토큰·체크포인트·실제 Git·승인)을 통과할 때만 최초 1회 적용한다.
 * 아직 도는 프로세스가 있는 턴은 감시 루프가 이어받는다. 적용이 시작된(applying) 턴은 어떤 경우에도 다시 적용하지 않는다.
 */
function recoverTurns(ex: Executor) {
  for (const t of Object.values(pipe(ex).turns)) {
    if (!RESTART_UNKNOWN.includes(t.status) || t.lifetime === ex.lifetime) continue;
    const execution = t.execId ? ex.state.executions[t.execId] : undefined;
    const running = t.status === 'launched' && execution && (['running', 'cancelling'].includes(execution.status) || (execution.completion && execution.completion.stage !== 'done'));
    if (running) continue;
    t.status = 'unknown'; t.failure = '서버 재시작 전 진행 중이던 턴 — 결과 불명, 재시도하지 않음';
    mark(ex, t.eventKeys, 'unknown', { reason: t.failure }, t.id);
  }
}

export async function pipelineTick(ex: Executor): Promise<void> {
  if (busy.has(ex) || ex.stopped) return;
  busy.add(ex);
  try {
    const rt = ex.runtime, s = rt.session;
    if (!s || rt.frozen) return;
    if (pipe(ex).launch) return;
    const limited = Object.values(pipe(ex).turns).find((t) => t.status === 'limited' && !t.limitHandledAt);
    if (limited) {
      limited.limitHandledAt = new Date().toISOString(); ex.store.save();
      return;
    }
    applyTakenOver(ex, s);
    let owner: ActionOwner | undefined, applying: MainTurn | undefined;
    if (s.status === 'applying' && s.actionLifetime === ex.lifetime) owner = s;
    else {
      if (!['completed', 'idle'].includes(s.status)) return;
      recoverTurns(ex);
      applying = Object.values(pipe(ex).turns).find((t) => t.status === 'applying' && t.lifetime === ex.lifetime);
      owner = applying;
    }
    if (owner) {
      let work;
      for (const row of owner.actionWork ?? []) if (row.status !== 'done') { work = row; break; }
      if (work?.status === 'dispatching') {
        if (work.action.type === 'push_main' && work.dispatchLifetime === ex.lifetime && work.pushStage) return; // 저장된 push는 실행 감시가 진행한다.
        else finishAction(ex, work, false, '서버 재시작 전 수행을 시작한 행동 — 결과 불명, 재시도하지 않음');
      } else if (work?.status === 'accepted') await authorizeAction(ex, s, owner, work);
      else if (work?.status === 'authorized') return; // 실행 감시가 저장된 authorized 행동을 직접 수행한다.
      if (actionsDone(owner)) {
        if (owner === s) finishSession(ex, s); else finishApplied(ex, applying!);
      }
      return;
    }
    applyVerified(ex);
    if (Object.values(pipe(ex).turns).some((t) => TURN_IN_FLIGHT.includes(t.status))) return;
    if (ex.stopped) return;
    const due = Object.values(pipe(ex).events).filter((e) => e.state === 'pending' && e.kind !== 'blocked' && !e.tried.includes(s.generation));
    if (!due.length) return;
    const eventKeys = [];
    for (const event of due) eventKeys.push(event.key);
    if (limitFor(ex, s.agent)) {
      const key = `limit-${s.generation}-${s.agent}`;
      pipe(ex).turns[key] = { id: key, sessionId: s.id, generation: s.generation, agent: s.agent, status: 'limited', eventKeys, startedAt: new Date().toISOString(), lifetime: ex.lifetime, tokenHash: '', checkpointFile: '', checkpointHash: '', actionResults: [], limitHandledAt: new Date().toISOString() };
      ex.store.save();
      return;
    }
    pipe(ex).launch = { sessionId: s.id, generation: s.generation, eventKeys, stage: 'queued' };
    ex.store.save();
  } catch (e) { ex.audit('pipeline_tick_error', { error: (e as Error).message }); } finally { busy.delete(ex); }
}
