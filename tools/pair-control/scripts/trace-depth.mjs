import path from 'node:path';

export function label(fn) { return path.basename(fn.file) + ':' + (fn.name ?? '<익명@' + fn.node.loc.start.line + '>'); }

export function computeDepths(ctx) {
  const colors = new Map();
  for (const start of ctx.fns) {
    if (colors.get(start) === 2) continue;
    const stack = [{ fn: start, index: 0, best: { depth: 0, path: [start], hows: [] } }]; colors.set(start, 1);
    while (stack.length) {
      const frame = stack[stack.length - 1], edges = ctx.graph.get(frame.fn) ?? [];
      if (frame.index >= edges.length) { ctx.depths.set(frame.fn, frame.best); colors.set(frame.fn, 2); stack.pop(); continue; }
      const edge = edges[frame.index];
      if (colors.get(edge.to) === 1) {
        const cycle = [];
        for (const ancestor of stack) cycle.push(label(ancestor.fn));
        cycle.push(label(edge.to)); ctx.cycles.push(cycle.join(' → ')); frame.index++; continue;
      }
      if (colors.get(edge.to) !== 2) { colors.set(edge.to, 1); stack.push({ fn: edge.to, index: 0, best: { depth: 0, path: [edge.to], hows: [] } }); continue; }
      const tail = ctx.depths.get(edge.to), depth = edge.w + tail.depth;
      if (depth > frame.best.depth) frame.best = { depth, path: [frame.fn, ...tail.path], hows: [edge.how, ...tail.hows] };
      frame.index++;
    }
  }
}
