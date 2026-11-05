export const MAX = 300;

export const clip = (s, n = MAX) => { const t = String(s ?? '').replace(/\s+$/, ''); return t.length > n ? t.slice(0, n) + ' …' : t; };

export function toolLine(name, input) {
  const i = input || {};
  return name === 'Bash' ? '$ ' + clip(i.command) : '[' + name + '] ' + clip(i.file_path || i.path || i.pattern || '', 160);
}

export function resultText(c) {
  return Array.isArray(c) ? c.map((b) => (b && b.text) || '').join('\n') : String(c ?? '');
}
