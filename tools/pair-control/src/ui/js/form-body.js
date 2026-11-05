import { specs } from './form-specs.js';

export function formBody() {
  const b = Object.fromEntries(new FormData(document.getElementById('assign')).entries());
  const [allowedFiles, conflictGroups, requiredModules, doneCriteria, readDocs] = [[b.allowedFiles, '\n'], [b.conflictGroups, ','], [b.requiredModules, ','], [b.doneCriteria, '\n'], [b.readDocs, '\n']]
    .map(([v, sep]) => String(v || '').split(sep).map((x) => x.trim()).filter(Boolean));
  return {
    ...b, allowedFiles, conflictGroups, requiredModules, doneCriteria, readDocs,
    checks: specs.c.map((c, i) => ({ id: 'c' + (i + 1), name: c.name || '검사 ' + (i + 1), executable: c.executable, args: c.args, cwd: c.cwd || '.' })),
    postChecks: specs.p.map((c, i) => ({ id: 'p' + (i + 1), name: c.name || '통합 후 검사 ' + (i + 1), executable: c.executable, args: c.args, cwd: '.' })),
  };
}
