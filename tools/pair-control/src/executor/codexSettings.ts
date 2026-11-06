import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type { ChargeRisk } from './chargeScan.ts';

export function scanCodexConfig(opts: { env?: NodeJS.ProcessEnv; home?: string } = {}): ChargeRisk[] {
  const env = opts.env ?? process.env;
  const home = opts.home ?? os.homedir();
  const file = path.join(env.CODEX_HOME || path.join(home, '.codex'), 'config.toml');
  if (!fs.existsSync(file)) return [];
  const label = file.startsWith(home + path.sep) ? `~${file.slice(home.length)}` : file;
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
  if ('profile' in top) risks.push({ code: 'settings_api_key', message: `선택된 Codex profile의 과금 경로를 확인할 수 없음: ${label}`, fix: '구독 전용 기본 설정을 확인하고 profile 선택 해제' });
  return risks;
}

export function codexLoginIsChatgpt(statusText: string | undefined): boolean {
  return !!statusText && /^\s*logged in using chatgpt\s*$/i.test(statusText);
}
