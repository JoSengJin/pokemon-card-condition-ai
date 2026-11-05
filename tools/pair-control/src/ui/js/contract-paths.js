export function bullets(text) {
  return text.split('\n').map((l) => l.trim()).filter((l) => /^([-*]|\d+[.)])\s+/.test(l)).map((l) => l.replace(/^([-*]|\d+[.)])\s+/, '').trim()).filter(Boolean);
}

export function pathOf(item) {
  const m = item.match(/^`([^`]+)`/) || item.match(/^([A-Za-z0-9_.\/-]+)(?:\s*\([^)]*\))?$/);
  const p = m && m[1].trim();
  if (!p || p.includes(' ') || !/^[A-Za-z0-9_.][A-Za-z0-9_.\/-]*$/.test(p)) return null;
  return m[0].startsWith('`') || /[\/.]/.test(p) ? p : null;
}

export function contractPaths(text, rejected) {
  return bullets(text).map((item) => { const p = pathOf(item); if (!p) rejected.push(item); return p; }).filter(Boolean);
}
