import { queueGuardCancellation } from './guardCancellation.ts';
// 구독 사용 한도 도달의 공급자별 처리.
// 한도 문구를 낸 실행의 공급자(메인 세션·구현 worker)를 구분해 그 공급자만 막고, 다른 공급자의 교대·실행은 막지 않는다.
// 같은 공급자는 worker든 메인이든 새 세션이든 사용자가 풀렸음을 확인하기 전에 시작하지 않는다(다른 세션으로 우회하지 않음).
// 출처를 알 수 없거나(실행 기록 없음) 공급자 실행이 아닌 출처(검사·리뷰)는 어느 공급자의 한도인지 알 수 없으므로 보수적으로 전역 한도로 둔다.
import { UserError, type Executor } from './executor.ts';
import type { Alert } from './freeGuard.ts';
import type { Agent } from './mainTypes.ts';

/** 한도 문구를 낸 출처 실행의 공급자. 구현 worker·메인 세션 실행이면 그 에이전트, 아니면 null(전역 차단). */
export function limitProvider(ex: Executor, source: string): { agent: Agent; kind: 'main' | 'agent' } | null {
  const src = ex.state.executions[source.replace(/^exec:/, '')];
  if (!src || (src.agent !== 'codex' && src.agent !== 'claude')) return null;
  return src.kind === 'main' ? { agent: src.agent, kind: 'main' } : (src.kind ?? 'agent') === 'agent' ? { agent: src.agent, kind: 'agent' } : null;
}

/** 공급자 차단은 감지 즉시 기록하고, 취소는 같은 저장의 요청을 감시가 수행한다. */
export function limitHandler(ex: Executor) {
  return function onLimitHit(alert: Alert) {
    const who = limitProvider(ex, alert.source);
    if (who) {
      ex.runtime.limited[who.agent] ??= { at: new Date().toISOString(), detail: alert.detail };
      ex.audit('agent_limit', { agent: who.agent, detail: alert.detail, via: who.kind });
      if (who.kind === 'agent') queueGuardCancellation(ex, '구독 한도 도달(공급자별)', who.agent);
      else ex.store.save();
      return;
    }
    if (ex.state.limit) return;
    ex.state.limit = { at: alert.at, detail: alert.detail, source: alert.source };
    ex.audit('limit_hit', { detail: alert.detail, source: alert.source });
    queueGuardCancellation(ex, '구독 한도 도달');
  };
}

/** 사용자가 그 에이전트의 한도가 풀렸음을 확인했을 때만 호출한다. */
export function clearAgentLimit(ex: Executor, agent: Agent) {
  if (!ex.runtime.limited[agent]) throw new UserError(`${agent}은(는) 한도 상태가 아님`);
  delete ex.runtime.limited[agent];
  ex.audit('main_limit_cleared', { agent });
  ex.store.save();
}
