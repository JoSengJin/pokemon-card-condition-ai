import { esc } from './core.js';

export function logRows(ui, id) {
  if (ui.log.id !== id) return [];
  const q = String(ui.keep.logFind || '').trim().toLowerCase();
  return q ? ui.log.rows.filter((r) => r.s.toLowerCase().includes(q)) : ui.log.rows;
}

export const KIND = [[/^\s*\$ /, 'info'], [/^\s*\[완료\] 정상/, 'ok'], [/^\s*(→\s*)?(오류|error|exception|traceback|fatal|failed|\[한도\])(?!\w)/i, 'bad'], [/^\s*(경고|warn(ing)?)\s*[:：]/i, 'warn'], [/^\s*(ok|ran \d+ tests?.*|.*\b\d+ passed\b.*|\[[\w./-]+ [0-9a-f]{7,}\].*)\s*$/i, 'ok']];

export function paintLines(rows) {
  const lines = [];
  for (const row of rows) {
    const safe = esc(row.s), kind = KIND.find((entry) => entry[0].test(row.s));
    lines.push('<span class="ln" data-t="' + row.t + '">' + (kind ? '<span class="' + kind[1] + '">' + safe + '</span>' : safe) + '</span>');
  }
  return lines.join('\n');
}
