import { PAID_ENV_KEYS } from './paidSignals.mjs';

export type ChargeCode = 'paid_env' | 'settings_api_key' | 'settings_login_method' | 'settings_unreadable' | 'forbidden_flag';

export interface ChargeRisk { code: ChargeCode; message: string; fix: string }

export const FORBIDDEN_FLAGS = ['--bare', '--max-budget-usd', '--betas'];

export function scanEnv(env: NodeJS.ProcessEnv = process.env): ChargeRisk[] {
  const found = PAID_ENV_KEYS.filter((k) => env[k]);
  return found.length
    ? [{ code: 'paid_env', message: `과금 경로가 열릴 수 있는 환경변수: ${found.join(', ')} (값은 읽지 않음)`, fix: '서버를 시작한 셸에서 unset 한 뒤 다시 시작' }]
    : [];
}

export function scanArgs(args: string[]): ChargeRisk[] {
  const bad = args.filter((a) => FORBIDDEN_FLAGS.some((f) => a === f || a.startsWith(`${f}=`)));
  return bad.length ? [{ code: 'forbidden_flag', message: `구독 로그인을 쓰지 않는 옵션: ${[...new Set(bad)].join(', ')}`, fix: '어댑터 인자에서 제거(코드 변경 필요)' }] : [];
}
