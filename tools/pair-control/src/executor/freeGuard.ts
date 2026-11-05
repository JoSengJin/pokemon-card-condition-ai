// 무료 전용 가드. 유료 과금 경로로 바뀔 수 있는 신호를 보면 서비스를 멈추고 사용자에게 알린다.
// 감지 대상:
//  1) 서버 환경의 API 키·클라우드 토큰(있으면 CLI가 구독 대신 API 과금 경로를 쓸 수 있음)
//  2) 실행 로그의 과금·크레딧·업그레이드 문구
//  3) 실제 모드 시작 시 구독 인증을 사용자가 확인하지 않은 경우(adapters.realPlan에서 시작 거부)
// 한계: 실제 청구 여부는 provider 계정에서만 확인 가능하다. 이 가드는 신호 기반 차단이다.
import fs from 'node:fs';
import path from 'node:path';
import { writeJsonAtomic } from './store.ts';
import { LIMIT_LOG_PATTERNS, PAID_ENV_KEYS, PAID_LOG_HARD, PAID_LOG_PATTERNS, PAID_LOG_SOFT } from './paidSignals.mjs';

export { PAID_ENV_KEYS, PAID_LOG_PATTERNS };

export interface Alert { at: string; reason: string; detail: string; source: string }

export class FreeGuard {
  readonly alertFile: string;
  constructor(stateDir: string, private onTrip: (a: Alert) => void, private onLimit: (a: Alert) => void = () => {}) {
    this.alertFile = path.join(stateDir, 'alerts', 'paid-risk.json');
  }

  pending(): Alert | null {
    try { return JSON.parse(fs.readFileSync(this.alertFile, 'utf8')); } catch { return null; }
  }

  checkEnv(env: NodeJS.ProcessEnv = process.env) {
    const found = PAID_ENV_KEYS.filter((k) => env[k]);
    if (found.length) this.trip('paid_env', `과금 경로가 열릴 수 있는 환경변수 존재: ${found.join(', ')} (값은 기록하지 않음)`, 'server-env');
  }

  /**
   * 우선순위: ① 확실한 과금 문구 → 서비스 종료 ② 구독 한도 도달 → 실행 정지(서비스는 유지) ③ 권유성 문구 → 서비스 종료.
   * 한도 안내문에 섞인 "extra usage" 같은 문구를 과금으로 오인해 서비스를 끄지 않되, 한도 상태에서는 어떤 구매·재시도도 하지 않는다.
   */
  scanLog(text: string, source: string): 'paid' | 'limit' | null {
    for (const re of PAID_LOG_HARD) {
      const m = text.match(re);
      if (m) { this.trip('paid_log', `실행 로그에서 과금 신호 문구 감지: "${m[0]}"`, source); return 'paid'; }
    }
    for (const re of LIMIT_LOG_PATTERNS) {
      const m = text.match(re);
      if (m) {
        this.onLimit({ at: new Date().toISOString(), reason: 'usage_limit', detail: `구독 사용 한도 도달 문구 감지: "${m[0]}"`, source });
        return 'limit';
      }
    }
    for (const re of PAID_LOG_SOFT) {
      const m = text.match(re);
      if (m) { this.trip('paid_log', `실행 로그에서 과금 신호 문구 감지: "${m[0]}"`, source); return 'paid'; }
    }
    return null;
  }

  trip(reason: string, detail: string, source: string) {
    const alert: Alert = { at: new Date().toISOString(), reason, detail, source };
    let exists = false;
    try { exists = !!JSON.parse(fs.readFileSync(this.alertFile, 'utf8')); } catch { /* no prior alert */ }
    if (!exists) writeJsonAtomic(this.alertFile, alert);
    this.onTrip(alert);
  }
}

export { sanitizedChildEnv, notifyUser } from './freeGuardEnv.ts';
