#!/usr/bin/env node
// 무료 가드 알림 확인/해제. 해제는 사용자가 원인을 확인한 뒤 직접 실행한다(자동 해제 없음).
//   npm run guard:status [-- --demo]   npm run guard:ack [-- --demo]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stateDir = process.env.PAIR_CONTROL_STATE_DIR ?? path.join(root, process.argv.includes('--demo') ? '.demo/state' : '.state');
const alertFile = path.join(stateDir, 'alerts', 'paid-risk.json');
const cmd = process.argv[2];

if (!fs.existsSync(alertFile)) { console.log('무료 가드: 알림 없음'); process.exit(0); }
const alert = JSON.parse(fs.readFileSync(alertFile, 'utf8'));
console.log(`무료 가드 알림 (${alert.at})\n  원인: ${alert.reason}\n  내용: ${alert.detail}\n  출처: ${alert.source}`);
if (cmd === 'ack') {
  const dest = path.join(path.dirname(alertFile), `acknowledged-${Date.now()}.json`);
  fs.renameSync(alertFile, dest);
  console.log(`확인 처리됨 → ${path.relative(root, dest)} (원인을 제거하지 않았다면 다시 발동합니다)`);
}
