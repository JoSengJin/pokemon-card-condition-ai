import fs from 'node:fs';
import path from 'node:path';
import { PAID_ENV_KEYS } from '../src/executor/paidSignals.mjs';
import { notify } from './launcher-notify.mjs';

function refuse(alertFile, detail) {
  fs.mkdirSync(path.dirname(alertFile), { recursive: true });
  if (!fs.existsSync(alertFile)) fs.writeFileSync(alertFile, JSON.stringify({ at: new Date().toISOString(), reason: 'paid_env', detail, source: 'launcher' }, null, 2));
  notify('유료 전환 신호 — 시작하지 않음', detail);
  process.exit(3);
}

export function enforceLauncherGuard(configFile, alertFile, demo) {

if (fs.existsSync(alertFile)) {
  const a = JSON.parse(fs.readFileSync(alertFile, 'utf8'));
  notify('이전 무료 가드 알림 미확인 — 시작하지 않음', `${a.detail} (확인 후 npm run guard:ack${demo ? ' -- --demo' : ''})`);
  process.exit(3);
}
const keys = PAID_ENV_KEYS.filter((k) => process.env[k]);
if (keys.length) refuse(alertFile, `과금 경로가 열릴 수 있는 환경변수: ${keys.join(', ')} — 셸에서 unset 후 다시 시작`);
if (!fs.existsSync(configFile)) {
  console.error(`설정 파일 없음: ${configFile}\nconfig.example.json을 복사해 config.local.json을 만들거나 npm run demo:fixture 후 npm start -- --demo`);
  process.exit(2);
}

}
