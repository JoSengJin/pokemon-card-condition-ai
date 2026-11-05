import { children } from './trace-ast.mjs';
import { exportedValue, namedFunction } from './trace-bindings.mjs';

export function objectIdentity(ctx, fn, base) {
  if (base === 'this') return fn.cls ? 'class:' + fn.cls : null;
  const scope = ctx.scopes.get(fn), suffix = [], seen = new Set();
  let local = scope?.locals.get(base);
  while (local?.alias && !seen.has(base)) { seen.add(base); suffix.unshift(...local.alias.chain); base = local.alias.base; local = scope?.locals.get(base); }
  const type = scope?.types[base] ?? local?.cls, tail = suffix.length ? '.' + suffix.join('.') : '';
  if (type && ctx.classes[type]) return 'class:' + type + tail;
  const imported = ctx.importsOf[fn.file]?.[base];
  const value = imported?.file ? exportedValue(ctx, imported.file, imported.imported) : ctx.values[fn.file + ':' + base];
  if (!value) return null;
  const cls = ctx.globalTypes[value.file + ':' + value.name];
  return (cls ? 'class:' + cls : 'value:' + value.file + ':' + value.name) + tail;
}

export function rememberValue(ctx, identity, expression, file) {
  const pending = [{ identity, expression }];
  while (pending.length) {
    const item = pending.pop(), node = item.expression;
    if (!node) continue;
    const target = node.__fn ?? (node.type === 'Identifier' ? namedFunction(ctx, file, node.name) : null);
    if (target) { const values = (ctx.members[item.identity] ??= []); if (!values.includes(target)) values.push(target); }
    if (node.type === 'ObjectExpression') for (const property of node.properties) {
      const key = property.key?.name ?? property.key?.value;
      if (key !== undefined) pending.push({ identity: item.identity + '.' + key, expression: property.value });
    }
  }
}

export function indexMembers(ctx) {
  ctx.members = {};
  for (const value of Object.values(ctx.values)) rememberValue(ctx, 'value:' + value.file + ':' + value.name, value.node, value.file);
  for (const module of ctx.modules) {
    const pending = [{ node: module.node.body, owner: module }];
    while (pending.length) {
      const frame = pending.pop(), node = frame.node, owner = node.__fn ?? frame.owner;
      if (node.type === 'AssignmentExpression' && node.left.type === 'MemberExpression' && !node.left.computed) {
        const parts = [node.left.property.name]; let base = node.left.object;
        while (base.type === 'MemberExpression' && !base.computed) { parts.unshift(base.property.name); base = base.object; }
        const identity = objectIdentity(ctx, owner, base.type === 'ThisExpression' ? 'this' : base.type === 'Identifier' ? base.name : null);
        if (identity) rememberValue(ctx, identity + '.' + parts.join('.'), node.right, module.file);
      }
      for (const child of children(node)) pending.push({ node: child, owner });
    }
  }
}

export function memberTargets(ctx, fn, call) {
  const identity = objectIdentity(ctx, fn, call.base);
  if (!identity) return [];
  const prefix = identity + (call.chain?.length ? '.' + call.chain.join('.') : '') + '.';
  if (!call.computed) return ctx.members[prefix + call.name] ?? [];
  const out = [];
  for (const [key, targets] of Object.entries(ctx.members)) if (key.startsWith(prefix) && !key.slice(prefix.length).includes('.')) out.push(...targets);
  return out;
}

export function constructorBindings(ctx) {
  ctx.constructorParams = {};
  for (const fn of ctx.fns) {
    if (!fn.cls || fn.name !== 'constructor') continue;
    const raw = ctx.parsed[fn.file].raw;
    for (const parameter of fn.node.params) {
      const id = parameter.type === 'AssignmentPattern' ? parameter.left : parameter;
      if (id.type !== 'Identifier') continue;
      const prefix = raw.slice(Math.max(0, id.start - 60), id.start);
      if (!/(private|protected|public|readonly)\s+$/.test(prefix)) continue;
      const annotation = raw.slice(id.end, parameter.type === 'AssignmentPattern' ? parameter.right.start : id.end + 100);
      if (/^\s*:\s*\([^)]*\)\s*=>/.test(annotation)) ctx.constructorParams[fn.cls + ':' + id.name] = { owner: fn, param: id.name };
    }
  }
}
