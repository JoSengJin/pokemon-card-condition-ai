import { execFile } from 'node:child_process';

export function notify(title, message) {
  const esc = (s) => String(s).replace(/["\\]/g, ' ').slice(0, 200);
  if (process.platform === 'darwin') execFile('osascript', ['-e', `display notification "${esc(message)}" with title "${esc(title)}" sound name "Basso"`], () => {});
  console.error(`\n[pair-control 무료 가드] ${title}: ${message}\n`);
}
