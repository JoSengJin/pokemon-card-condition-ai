import { codexLoginIsChatgpt, scanArgs, scanClaudeSettings, scanCodexConfig, scanEnv, type ChargeRisk } from './nocharge.ts';
import type { Probe } from './adapterProbe.ts';
import type { PairConfig } from './config.ts';

export function chargeRisks(agent: 'codex' | 'claude', cfg: PairConfig, ctx: { worktree?: string; env?: NodeJS.ProcessEnv; args?: string[] } = {}): ChargeRisk[] {
  const home = cfg.homeDir;
  return [
    ...scanEnv(ctx.env ?? process.env),
    ...(agent === 'claude' ? scanClaudeSettings({ worktree: ctx.worktree, env: ctx.env, home }) : scanCodexConfig({ env: ctx.env, home })),
    ...(ctx.args ? scanArgs(ctx.args) : []),
  ];
}

export type BlockerCode = 'cli_missing' | 'cli_error' | 'flags_unverified' | 'real_calls_disabled' | 'subscription_unconfirmed' | 'not_checked'
  | 'paid_env' | 'login_not_chatgpt' | 'settings_api_key' | 'settings_login_method' | 'settings_unreadable' | 'forbidden_flag' | 'limit_hit';

export interface Blocker { code: BlockerCode; message: string; fix: string }

export function realReadiness(agent: 'codex' | 'claude', p: Probe | undefined, cfg: PairConfig, ctx: { worktree?: string; limit?: { detail: string } | null; env?: NodeJS.ProcessEnv } = {}): { available: boolean; blockers: Blocker[] } {
  const b: Blocker[] = [];
  if (!p) b.push({ code: 'not_checked', message: 'CLI 확인 전', fix: '"CLI 다시 확인"을 누르세요(--version/--help만 실행)' });
  else if (!p.installed && !p.binary) b.push({ code: 'cli_missing', message: `${agent} CLI 미설치`, fix: `${agent} CLI를 설치하거나 config.cli.${agent}에 실행 파일 경로를 지정` });
  else if (!p.installed) b.push({ code: 'cli_error', message: `${agent} 실행 실패: ${p.note}`, fix: '터미널에서 --version이 동작하는지 확인' });
  else if (p.missingFlags.length) b.push({ code: 'flags_unverified', message: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}`, fix: 'CLI 버전을 확인하고 어댑터 옵션을 갱신(별도 작업)' });
  if (agent === 'codex' && p?.installed && !codexLoginIsChatgpt(p.loginStatus)) {
    b.push({ code: 'login_not_chatgpt', message: `codex 로그인이 ChatGPT 구독으로 확인되지 않음(${p.loginStatus || '출력 없음'})`, fix: '`codex login`으로 ChatGPT 로그인(API 키 로그인은 API 요금)' });
  }
  if (!cfg.allowRealModelCalls) b.push({ code: 'real_calls_disabled', message: '실제 모델 호출 차단(기본값)', fix: '별도 승인 작업에서 config.allowRealModelCalls=true' });
  if (!cfg.confirmedSubscriptionAuth) b.push({ code: 'subscription_unconfirmed', message: '구독 로그인·추가 크레딧 꺼짐 미확인', fix: '계정에서 구독 로그인(API 키 아님)과 추가 사용 크레딧이 꺼져 있음을 직접 확인한 뒤 config.confirmedSubscriptionAuth=true' });
  const home = cfg.homeDir;
  const risks = [
    ...scanEnv(ctx.env ?? process.env),
    ...(agent === 'claude' ? scanClaudeSettings({ worktree: ctx.worktree, env: ctx.env, home }) : scanCodexConfig({ env: ctx.env, home })),
  ];
  for (const r of risks) b.push({ code: r.code, message: r.message, fix: r.fix });
  if (ctx.limit) b.push({ code: 'limit_hit', message: `구독 사용 한도 도달 상태: ${ctx.limit.detail}`, fix: '한도가 풀린 것을 확인한 뒤 "한도 해제 확인"(재시도·크레딧 구매는 하지 않음)' });
  return { available: b.length === 0, blockers: b };
}
