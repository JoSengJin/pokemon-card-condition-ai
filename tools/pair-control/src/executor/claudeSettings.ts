import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PAID_ENV_KEYS } from './paidSignals.mjs';
import type { ChargeRisk } from './chargeScan.ts';

export function scanClaudeSettings(opts: { worktree?: string; env?: NodeJS.ProcessEnv; home?: string } = {}): ChargeRisk[] {
  const env = opts.env ?? process.env;
  const home = opts.home ?? os.homedir();
  const userDir = env.CLAUDE_CONFIG_DIR || path.join(home, '.claude');
  const files = [path.join(userDir, 'settings.json')];
  if (opts.worktree) files.push(path.join(opts.worktree, '.claude', 'settings.json'), path.join(opts.worktree, '.claude', 'settings.local.json'));
  const risks: ChargeRisk[] = [];
  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const label = file.startsWith(home + path.sep) ? `~${file.slice(home.length)}` : file;
    let json: any;
    try { json = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {
      risks.push({ code: 'settings_unreadable', message: `Claude 설정을 읽지 못해 API 키 설정 여부를 확인할 수 없음: ${label}`, fix: '파일을 직접 확인하고 JSON 오류를 고치거나, apiKeyHelper·API 키가 없음을 확인' });
      continue;
    }
    if (json && typeof json === 'object') {
      if (json.apiKeyHelper) risks.push({ code: 'settings_api_key', message: `apiKeyHelper가 설정됨: ${label}`, fix: '구독 로그인만 쓰려면 이 설정을 제거' });
      if (json.env && typeof json.env === 'object') {
        const names = [];
        for (const key of PAID_ENV_KEYS) if (key in json.env) names.push(key);
        if (names.length) risks.push({ code: 'settings_api_key', message: `설정의 env에 API 키 항목 이름이 있음(${names.join(', ')}): ${label} — 값은 읽지 않음`, fix: '해당 항목을 제거' });
      }
      if (json.forceLoginMethod !== undefined && json.forceLoginMethod !== 'claudeai') {
        risks.push({ code: 'settings_login_method', message: `forceLoginMethod가 claudeai가 아님(${String(json.forceLoginMethod).slice(0, 30)}): ${label}`, fix: '구독(claude.ai) 로그인만 쓰도록 설정하거나 항목을 제거(값 이름은 문서 목차에 없어 보수적으로 차단)' });
      }
    }
  }
  return risks;
}
