#!/usr/bin/env node
// 관제 서버 실행기. `mastra dev`(Studio + /pair 화면)를 자신의 자식 프로세스 그룹으로 띄우고,
// 무료 가드 알림이 생기면 그 그룹만 종료한 뒤 사용자에게 알린다. 다른 서버·세션은 건드리지 않는다.
//   npm start                → config.local.json, .state/
//   npm start -- --demo      → .demo/config.json, .demo/state (npm run demo:fixture 먼저)
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { notify } from './launcher-notify.mjs';
import { enforceLauncherGuard } from './launcher-guard.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
if (Number(process.versions.node.split('.')[0]) < 22) {
  console.error(`Node ${process.versions.node}는 지원하지 않습니다(>=22 필요). nvm use 24 등으로 바꾼 뒤 다시 실행하세요.`);
  process.exit(2);
}
const demo = process.argv.includes('--demo');
const configFile = process.env.PAIR_CONTROL_CONFIG ?? path.join(root, demo ? '.demo/config.json' : 'config.local.json');
const stateDir = process.env.PAIR_CONTROL_STATE_DIR ?? path.join(root, demo ? '.demo/state' : '.state');
const alertFile = path.join(stateDir, 'alerts', 'paid-risk.json');

enforceLauncherGuard(configFile, alertFile, demo);

const env = {
  ...process.env, PAIR_CONTROL_ROOT: root, PAIR_CONTROL_CONFIG: configFile, PAIR_CONTROL_STATE_DIR: stateDir,
  MASTRA_TELEMETRY_DISABLED: '1',
};
const port = JSON.parse(fs.readFileSync(configFile, 'utf8')).port ?? 4111;
const child = spawn(path.join(root, 'node_modules', '.bin', 'mastra'), ['dev'], { cwd: root, env, stdio: 'inherit', detached: true });
console.log(`[pair-control] mastra dev pid=${child.pid} · 관제 http://127.0.0.1:${port}/pair · Studio http://127.0.0.1:${port}/`);

let stopping = false, stopCode = 0;
function stopChild(reason, code) {
  if (stopping) return; stopping = true; stopCode = code;
  console.error(`[pair-control] 종료: ${reason}`);
  try { process.kill(-child.pid, 'SIGTERM'); } catch { /* gone */ }
  setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL'); } catch { /* gone */ } process.exit(code); }, 5000).unref();
}

const watch = setInterval(() => {
  if (!fs.existsSync(alertFile)) return;
  clearInterval(watch);
  const a = JSON.parse(fs.readFileSync(alertFile, 'utf8'));
  notify('유료 전환 신호 감지 — 서비스 종료', a.detail);
  stopChild(`무료 가드: ${a.detail}`, 3);
}, 1000);
process.on('SIGINT', () => stopChild('SIGINT', 0));
process.on('SIGTERM', () => stopChild('SIGTERM', 0));
child.on('exit', (code) => { clearInterval(watch); process.exit(stopping ? stopCode : code ?? 0); });
