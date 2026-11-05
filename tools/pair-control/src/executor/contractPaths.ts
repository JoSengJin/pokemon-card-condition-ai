import { FORBIDDEN_PREFIXES, FORBIDDEN_FILES } from './contractConstants.ts';

export function isForbidden(f: string) {
  for (const prefix of FORBIDDEN_PREFIXES) if (f === prefix.slice(0, -1) || f.startsWith(prefix)) return true;
  return FORBIDDEN_FILES.includes(f) || /(^|\/)labels[^/]*\.jsonl$/.test(f);
}

export function pathsOverlap(a: string, b: string) {
  if (a === b) return true;
  const ad = a.endsWith('/'), bd = b.endsWith('/');
  if (ad && b.startsWith(a)) return true;
  if (bd && a.startsWith(b)) return true;
  return false;
}

export function isAllowed(file: string, allowed: string[]) {
  for (const path of allowed) if (path.endsWith('/') ? file.startsWith(path) : file === path) return true;
  return false;
}
