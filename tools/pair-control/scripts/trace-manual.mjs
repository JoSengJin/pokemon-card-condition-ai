import fs from 'node:fs';
import path from 'node:path';

export function findByLabel(ctx, label) {
  const [file, name] = label.split(':'), out = [];
  for (const fn of ctx.fns) if (path.basename(fn.file) === file && fn.name === name) out.push(fn);
  return out;
}

export function applyManual(ctx) {
  const file = path.join(ctx.root, 'scripts', 'structure-edges.json');
  ctx.manual = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')).edges ?? [] : [];
  for (const edge of ctx.manual) {
    if (!edge.evidence) throw new Error('수동 간선에는 근거(evidence)가 필요함: ' + edge.from + ' -> ' + edge.to);
    const from = findByLabel(ctx, edge.from), to = findByLabel(ctx, edge.to);
    if (!from.length || !to.length) throw new Error('수동 간선의 호출자 또는 대상이 존재하지 않음: ' + edge.from + ' -> ' + edge.to);
    if (edge.via && !from.some((fn) => ctx.parsed[fn.file].orig.slice(fn.node.start, fn.node.end).includes(edge.via))) throw new Error('수동 간선 근거 문구(' + edge.via + ')가 호출자 본문에 없음: ' + edge.from);
    for (const caller of from) for (const target of to) ctx.graph.get(caller).push({ to: target, w: edge.weight ?? 1, how: 'manual: ' + edge.evidence });
  }
  const unresolved = [];
  for (const call of ctx.unresolved) {
    let resolved = false;
    for (const edge of ctx.manual) {
      if (!(edge.resolves ?? []).includes(call.call)) continue;
      for (const fn of findByLabel(ctx, edge.from)) if (fn.name === call.caller && path.basename(fn.file) === path.basename(call.file)) resolved = true;
    }
    if (!resolved) unresolved.push(call);
  }
  ctx.unresolved = unresolved;
}
