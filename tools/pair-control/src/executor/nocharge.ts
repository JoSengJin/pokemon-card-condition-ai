// 실제 CLI 모드의 무과금 조건 검사. 구독 로그인 대신 API 과금 경로로 빠질 수 있는 설정을 시작 전에 찾아 막는다.
// 값은 읽어서 기록하지 않는다: 환경변수는 이름만, Claude 설정은 키 이름과 forceLoginMethod 값만 본다.
// 자격 증명 파일(auth.json, 키체인)은 열지 않는다. 로그인 방식을 코드로 알아내는 명령은 두 CLI 문서에서 찾지 못했으므로
// 마지막 방어선은 사용자가 확인했다는 표시(confirmedSubscriptionAuth)다.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PAID_ENV_KEYS } from './paidSignals.mjs';

export type ChargeCode = 'paid_env' | 'settings_api_key' | 'settings_login_method' | 'settings_unreadable' | 'forbidden_flag';
export interface ChargeRisk { code: ChargeCode; message: string; fix: string }

/** 구독 로그인을 쓰지 않거나 API 사용자용인 옵션. --bare는 문서에 "구독 로그인을 쓰지 않는다"고 명시되어 있다. */
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

const tilde = (p: string, home: string) => (p.startsWith(home + path.sep) ? `~${p.slice(home.length)}` : p);

/** Claude Code 설정 파일 위치: 사용자 ~/.claude/settings.json(CLAUDE_CONFIG_DIR가 있으면 그 폴더), 프로젝트 .claude/settings(.local).json */
export function claudeSettingsFiles(opts: { worktree?: string; env?: NodeJS.ProcessEnv; home?: string } = {}) {
  const env = opts.env ?? process.env;
  const home = opts.home ?? os.homedir();
  const userDir = env.CLAUDE_CONFIG_DIR || path.join(home, '.claude');
  const files = [path.join(userDir, 'settings.json')];
  if (opts.worktree) files.push(path.join(opts.worktree, '.claude', 'settings.json'), path.join(opts.worktree, '.claude', 'settings.local.json'));
  return { files, home };
}

/**
 * apiKeyHelper(명령으로 API 자격을 만듦), env(모든 세션에 환경변수 주입 — API 키를 넣을 수 있음), forceLoginMethod(claude.ai 외 로그인)를 찾는다.
 * 읽을 수 없는 설정 파일은 확인할 수 없으므로 막는다.
 */
export function scanClaudeSettings(opts: { worktree?: string; env?: NodeJS.ProcessEnv; home?: string } = {}): ChargeRisk[] {
  const { files, home } = claudeSettingsFiles(opts);
  const risks: ChargeRisk[] = [];
  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const label = tilde(file, home);
    let json: any;
    try { json = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {
      risks.push({ code: 'settings_unreadable', message: `Claude 설정을 읽지 못해 API 키 설정 여부를 확인할 수 없음: ${label}`, fix: '파일을 직접 확인하고 JSON 오류를 고치거나, apiKeyHelper·API 키가 없음을 확인' });
      continue;
    }
    if (json && typeof json === 'object') {
      if (json.apiKeyHelper) risks.push({ code: 'settings_api_key', message: `apiKeyHelper가 설정됨: ${label}`, fix: '구독 로그인만 쓰려면 이 설정을 제거' });
      if (json.env && typeof json.env === 'object') {
        const names = PAID_ENV_KEYS.filter((k) => k in json.env);
        if (names.length) risks.push({ code: 'settings_api_key', message: `설정의 env에 API 키 항목 이름이 있음(${names.join(', ')}): ${label} — 값은 읽지 않음`, fix: '해당 항목을 제거' });
      }
      if (json.forceLoginMethod !== undefined && json.forceLoginMethod !== 'claudeai') {
        risks.push({ code: 'settings_login_method', message: `forceLoginMethod가 claudeai가 아님(${String(json.forceLoginMethod).slice(0, 30)}): ${label}`, fix: '구독(claude.ai) 로그인만 쓰도록 설정하거나 항목을 제거(값 이름은 문서 목차에 없어 보수적으로 차단)' });
      }
    }
  }
  return risks;
}

/** Codex 설정 위치: $CODEX_HOME/config.toml(없으면 ~/.codex). 프로젝트 .codex/config.toml은 공급자 키를 무시한다(공식 문서). */
export function codexConfigFile(opts: { env?: NodeJS.ProcessEnv; home?: string } = {}) {
  const env = opts.env ?? process.env;
  const home = opts.home ?? os.homedir();
  return { file: path.join(env.CODEX_HOME || path.join(home, '.codex'), 'config.toml'), home };
}

/**
 * TOML 파서 없이 줄 단위로 최상위 키만 본다(표 아래 키는 무시). 값은 forced_login_method·model_provider의 문자열만 읽고 나머지는 존재만 본다.
 * 막는 것: forced_login_method가 chatgpt가 아님(api면 API 요금), model_provider가 openai가 아님(다른 공급자·키), openai_base_url(기본 엔드포인트 변경).
 * 설정 파일에 키가 없으면 통과이며 실제 로그인 방식은 `codex login status`로 따로 확인한다(adapters.ts).
 */
export function scanCodexConfig(opts: { env?: NodeJS.ProcessEnv; home?: string } = {}): ChargeRisk[] {
  const { file, home } = codexConfigFile(opts);
  if (!fs.existsSync(file)) return [];
  const label = tilde(file, home);
  let text: string;
  try { text = fs.readFileSync(file, 'utf8'); } catch {
    return [{ code: 'settings_unreadable', message: `Codex 설정을 읽지 못해 과금 경로 설정을 확인할 수 없음: ${label}`, fix: '파일 권한을 확인하거나 설정을 직접 점검' }];
  }
  const top: Record<string, string> = {};
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (line.startsWith('[')) break; // 첫 표 이후는 최상위 키가 아니다
    const m = line.match(/^([A-Za-z0-9_]+)\s*=\s*(.*)$/);
    if (m) top[m[1]] = m[2].replace(/\s+#.*$/, '').trim().replace(/^["']|["']$/g, '');
  }
  const risks: ChargeRisk[] = [];
  if ('forced_login_method' in top && top.forced_login_method !== 'chatgpt') {
    risks.push({ code: 'settings_login_method', message: `forced_login_method가 chatgpt가 아님(${top.forced_login_method.slice(0, 30)}): ${label}`, fix: 'chatgpt로 바꾸거나 제거' });
  }
  if ('model_provider' in top && top.model_provider !== 'openai') {
    risks.push({ code: 'settings_api_key', message: `model_provider가 openai가 아님(${top.model_provider.slice(0, 30)}): ${label} — 다른 공급자는 별도 키·요금`, fix: '구독 로그인만 쓰려면 제거' });
  }
  if ('openai_base_url' in top) risks.push({ code: 'settings_api_key', message: `openai_base_url이 설정됨: ${label}`, fix: '구독 로그인만 쓰려면 제거' });
  return risks;
}

/** `codex login status`의 출력이 ChatGPT 로그인임을 말하는지. 그 밖(API 키·로그아웃·알 수 없음)은 모두 차단한다. 자격 증명 파일은 열지 않는다. */
export function codexLoginIsChatgpt(statusText: string | undefined): boolean {
  return !!statusText && /logged in using chatgpt/i.test(statusText);
}
