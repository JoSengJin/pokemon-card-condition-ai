import { FORBIDDEN_PREFIXES, FORBIDDEN_FILES } from './contractConstants.ts';

export function isForbidden(f: string) {
  return FORBIDDEN_PREFIXES.some((p) => f === p.slice(0, -1) || f.startsWith(p)) || FORBIDDEN_FILES.includes(f) || /(^|\/)labels[^/]*\.jsonl$/.test(f);
}

export function pathsOverlap(a: string, b: string) {
  if (a === b) return true;
  const ad = a.endsWith('/'), bd = b.endsWith('/');
  if (ad && b.startsWith(a)) return true;
  if (bd && a.startsWith(b)) return true;
  return false;
}

export function isAllowed(file: string, allowed: string[]) {
  return allowed.some((a) => (a.endsWith('/') ? file.startsWith(a) : file === a));
}
