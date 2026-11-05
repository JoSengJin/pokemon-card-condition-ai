import { LIMIT_DEFS, LIMIT_DEPTH } from './trace-config.mjs';
import { label } from './trace-depth.mjs';

export function resultOf(ctx, only) {
  const counts = {}, overFiles = [], starts = [], overStarts = [], external = {};
  for (const file of ctx.files) { const defs = ctx.byFile[file]?.length ?? 0; counts[file] = defs; if (defs > LIMIT_DEFS) overFiles.push({ file, defs }); }
  for (const fn of ctx.fns) {
    if (only && fn.name !== only) continue;
    const trace = ctx.depths.get(fn), path = [];
    for (const step of trace.path) path.push(label(step));
    const row = { start: label(fn), transitions: trace.depth, path: path.join(' → '), hows: trace.hows };
    if (only) { const callees = new Set(); for (const edge of ctx.graph.get(fn)) callees.add(label(edge.to)); row.callees = [...callees]; }
    starts.push(row); if (row.transitions > LIMIT_DEPTH) overStarts.push(row);
  }
  overStarts.sort((a, b) => b.transitions - a.transitions);
  for (const call of ctx.external) { const kind = call.reason; (external[kind] ??= { count: 0, sample: call.file + ':' + call.line + ' ' + call.call }).count++; }
  return only ? { perFile: counts, starts, unresolvedCount: ctx.unresolved.length, cycles: ctx.cycles } : { limits: { defs: LIMIT_DEFS, depth: LIMIT_DEPTH }, perFile: counts, starts, overFiles, overStarts, unresolved: ctx.unresolved, external, externalCalls: ctx.external, manualEdges: ctx.manual.length, cycles: ctx.cycles };
}
