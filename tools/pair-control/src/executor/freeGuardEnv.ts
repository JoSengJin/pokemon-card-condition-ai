import { execFile } from 'node:child_process';
import { PAID_ENV_KEYS } from './paidSignals.mjs';

export function sanitizedChildEnv(base: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const keep = ['PATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'LC_ALL', 'TMPDIR', 'TERM'];
  const env: NodeJS.ProcessEnv = {};
  for (const k of keep) if (base[k]) env[k] = base[k];
  for (const k of PAID_ENV_KEYS) delete env[k];
  env.MASTRA_TELEMETRY_DISABLED = '1';
  return env;
}

/** macOS 알림(무료, 로컬). 실패해도 알림 파일과 콘솔 출력은 남는다. */
export function notifyUser(title: string, message: string) {
  const words = [title, message];
  for (let i = 0; i < words.length; i++) words[i] = words[i].replace(/["\\]/g, ' ').slice(0, 200);
  if (process.platform === 'darwin' && !process.env.PAIR_CONTROL_NO_NOTIFY) {
    execFile('osascript', ['-e', `display notification "${words[1]}" with title "${words[0]}" sound name "Basso"`]).on('error', () => {});
  }
  console.error(`\n[pair-control 무료 가드] ${title}: ${message}\n`);
}
