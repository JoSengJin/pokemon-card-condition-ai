export function logRows(ui, id) {
  if (ui.log.id !== id) return [];
  const q = String(ui.keep.logFind || '').trim().toLowerCase();
  return q ? ui.log.rows.filter((r) => r.s.toLowerCase().includes(q)) : ui.log.rows;
}

export const HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };

export const KIND = [[/^\s*\$ /, 'info'], [/^\s*\[완료\] 정상/, 'ok'], [/^\s*(→\s*)?(오류|error|exception|traceback|fatal|failed|\[한도\])(?!\w)/i, 'bad'], [/^\s*(경고|warn(ing)?)\s*[:：]/i, 'warn'], [/^\s*(ok|ran \d+ tests?.*|.*\b\d+ passed\b.*|\[[\w./-]+ [0-9a-f]{7,}\].*)\s*$/i, 'ok']];

export function paintLines(rows) {
  return rows.map((r) => {
    const safe = r.s.replace(/[&<>"]/g, (c) => HTML[c]), kind = KIND.find((k) => k[0].test(r.s));
    return '<span class="ln" data-t="' + r.t + '">' + (kind ? '<span class="' + kind[1] + '">' + safe + '</span>' : safe) + '</span>';
  }).join('\n');
}
