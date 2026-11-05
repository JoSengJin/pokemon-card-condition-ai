import { LIMIT_LOG_PATTERNS, PAID_LOG_HARD, PAID_LOG_SOFT } from './paidSignals.mjs';
import type { Alert } from './freeGuard.ts';

export type GuardSignal = { kind: 'paid'; reason: string; detail: string; source: string } | { kind: 'limit'; alert: Alert };

/** 과금 확정 → 공급자 한도 → 과금 권유 순서. 감지만 하며 상태·프로세스를 바꾸지 않는다. */
export function textSignal(text: string, source: string): GuardSignal | null {
  for (const pattern of PAID_LOG_HARD) {
    const match = text.match(pattern);
    if (match) return { kind: 'paid', reason: 'paid_log', detail: '실행 로그에서 과금 신호 문구 감지: "' + match[0] + '"', source };
  }
  for (const pattern of LIMIT_LOG_PATTERNS) {
    const match = text.match(pattern);
    if (match) return { kind: 'limit', alert: { at: new Date().toISOString(), reason: 'usage_limit', detail: '구독 사용 한도 도달 문구 감지: "' + match[0] + '"', source } };
  }
  for (const pattern of PAID_LOG_SOFT) {
    const match = text.match(pattern);
    if (match) return { kind: 'paid', reason: 'paid_log', detail: '실행 로그에서 과금 신호 문구 감지: "' + match[0] + '"', source };
  }
  return null;
}
