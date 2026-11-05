import { textSignal, type GuardSignal } from './guardSignal.ts';
// 스트리밍(JSONL) 출력용 무과금 가드. 구조화된 이벤트는 신호가 되는 필드만 검사하고, 내용 이벤트는 건너뛴다.
// 이유: 스트리밍에는 에이전트가 읽은 파일·쓴 코드가 그대로 들어온다. 전체를 과금 문구로 검색하면 paidSignals.mjs 같은 파일을
// 읽기만 해도 서비스가 종료된다. 구조화 이벤트가 아닌 줄(텍스트 모드·stderr)은 지금처럼 글 전체를 검사한다.
import type { FreeGuard } from './freeGuard.ts';

/** 이 값이면 CLI가 구독 로그인이 아니라 API 키 경로로 인증했다는 뜻이다(Claude init 이벤트의 apiKeySource). */
const API_KEY_SOURCES = ['user', 'project', 'org', 'temporary'];
const BILLING = /(billing|payment|credit|quota)/i;

type Signal = { trip: string } | { scan: string } | null;

/** 이벤트 하나에서 검사할 것만 골라낸다. 내용 이벤트(assistant/user/item.*)는 null. */
export function eventSignal(o: any): Signal {
  if (o.type === 'system' && o.subtype === 'init' && API_KEY_SOURCES.includes(String(o.apiKeySource))) return { trip: `Claude가 API 키 경로로 인증됨(apiKeySource=${o.apiKeySource}) — 구독 로그인이 아님` };
  const err = typeof o.error === 'string' ? o.error : o.error?.message;
  if (err) return BILLING.test(err) ? { trip: `실행 이벤트의 결제·크레딧 오류: ${String(err).slice(0, 120)}` } : { scan: `Claude Code 이벤트 error=${String(err).slice(0, 200)}` + (/rate[_ ]?limit/i.test(err) ? ' — limit reached' : '') };
  if (o.type === 'rate_limit_event' && o.rate_limit_info?.status === 'rejected') return { scan: '구독 사용 한도 거절 이벤트 — limit reached' };
  if ((o.type === 'result' && o.is_error) || o.type === 'error' || o.type === 'turn.failed') return { scan: String(o.result ?? o.message ?? o.error?.message ?? '') };
  return null;
}

/**
 * 읽은 로그 조각을 줄 단위로 검사한다. 구조화 이벤트({"type":…} JSON 한 줄)는 eventSignal로, 나머지 줄은 기존 scanLog로.
 * 서비스 종료·알림은 FreeGuard.trip/scanLog가 하는 그대로다.
 */
export function outputSignals(text: string, source: string): GuardSignal[] {
  const signals: GuardSignal[] = [];
  for (const line of text.split('\n')) {
    if (!line.trim()) continue;
    let event: any = null;
    if (line.startsWith('{')) { try { event = JSON.parse(line); } catch { /* raw text */ } }
    const structured = event && typeof event.type === 'string';
    const signal = structured ? eventSignal(event) : { scan: line };
    if (!signal) continue;
    if ('trip' in signal) signals.push({ kind: 'paid', reason: 'paid_stream', detail: signal.trip, source });
    else { const observed = textSignal(signal.scan, source); if (observed) signals.push(observed); }
  }
  return signals;
}

export function scanOutput(guard: FreeGuard, text: string, source: string) {
  for (const signal of outputSignals(text, source)) {
    if (signal.kind === 'paid') guard.trip(signal.reason, signal.detail, signal.source);
    else guard.reportLimit(signal.alert);
  }
}
